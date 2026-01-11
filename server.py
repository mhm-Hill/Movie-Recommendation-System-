from http.server import SimpleHTTPRequestHandler, HTTPServer
import urllib.parse
import pymysql
from jinja2 import Environment, FileSystemLoader
import os
from http import cookies
import uuid
import math
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import json
from werkzeug.security import generate_password_hash, check_password_hash


PORT = 8000
sessions = {}
env = Environment(loader=FileSystemLoader('templates'))


def connect_db():
    try:
        connection = pymysql.connect(
            host='localhost', user='root', password='', db='movie',
            charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except pymysql.MySQLError as e:
        print(f"Error connecting to MySQL Database: {e}")
        return None


class MyHandler(SimpleHTTPRequestHandler):
    
   
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path_only = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if path_only.startswith('/static/'):
            return super().do_GET()

        public_pages = {'/': 'login.html', '/login': 'login.html', '/register': 'register.html'}
        if path_only in public_pages:
            return self.serve_template(public_pages[path_only], {'query_params': query_params})

        user_id = self.get_session_user()
        if not user_id:
            return self.redirect('/login')

        if path_only.startswith('/admin'):
            return self.handle_admin_page()

        user_routes = {
            '/dashboard': lambda: self.serve_template('dashboard.html'),
            '/recommend': lambda: self.serve_template('recommend.html'),
            '/final': lambda: self.serve_template('final.html'),
            '/profile': lambda: self.handle_profile(user_id),
            '/browse': lambda: self.handle_browse(user_id),
            '/movie': lambda: self.handle_movie_details(),
            '/logout': self.handle_logout
        }
        
        handler = user_routes.get(path_only)
        if handler:
            handler()
        else:
            self.send_error(404, 'Page Not Found')

    def do_POST(self):
        try:
            path_only = urllib.parse.urlparse(self.path).path
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = urllib.parse.parse_qs(post_data.decode('utf-8'))
        except Exception as e:
            print(f"Error processing POST request: {e}")
            return self.send_error(400, "Bad POST request")

        if path_only.startswith('/admin'):
            return self.handle_admin_post_requests(path_only, data)
        
        routes = {
            '/login': self.handle_login, '/register': self.handle_register,
            '/recommend': self.handle_recommend, '/rate_movie': self.handle_rating,
            '/toggle_watchlist': self.handle_toggle_watchlist, '/update_profile': self.handle_update_profile
        }
        handler = routes.get(path_only)
        if handler:
            handler(data)
        else:
            self.send_error(404, 'POST path not found')

    
    def serve_template(self, template_name, context=None):
        if context is None: context = {}
        try:
            template = env.get_template(template_name)
            session_info = self.get_session_info()
            if session_info:
                context['is_admin_session'] = session_info.get('is_admin', False)
                context['user_id_session'] = session_info.get('user_id')
            html = template.render(context)
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        except Exception as e:
            print(f"Template error for {template_name}: {e}")
            self.send_error(500, f"Template error: {e}")

    def redirect(self, location):
        self.send_response(303)
        self.send_header('Location', location)
        self.end_headers()

    def set_cookie(self, key, value, path='/', max_age=None):
        c = cookies.SimpleCookie()
        c[key] = value
        c[key]["path"] = path
        if max_age is not None: c[key]["max-age"] = max_age
        self.send_header("Set-Cookie", c.output(header='', sep=''))

    def get_session_info(self):
        if "Cookie" in self.headers:
            cookie = cookies.SimpleCookie(self.headers["Cookie"])
            session_id_morsel = cookie.get("session_id")
            if session_id_morsel: return sessions.get(session_id_morsel.value)
        return None

    def get_session_user(self):
        session_info = self.get_session_info()
        return session_info.get('user_id') if session_info else None

    def is_admin(self):
        session_info = self.get_session_info()
        return session_info.get('is_admin', False) if session_info else False

    
    def handle_login(self, data):
        email = data.get('email', [''])[0]
        password = data.get('password', [''])[0]
        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT User_id, Password, is_admin FROM users WHERE Email=%s", (email,))
                user = cursor.fetchone()
            if user and check_password_hash(user['Password'], password):
                session_id_val = str(uuid.uuid4())
                sessions[session_id_val] = {'user_id': user['User_id'], 'is_admin': user['is_admin']}
                self.send_response(303)
                self.set_cookie("session_id", session_id_val, max_age=3600)
                self.send_header('Location', '/dashboard')
                self.end_headers()
            else: self.redirect('/login?error=invalid_credentials')
        finally:
            if connection: connection.close()

    def handle_register(self, data):
        name = data.get('name', [''])[0]
        email = data.get('email', [''])[0]
        password = data.get('password', [''])[0]
        if not name or not email or not password: return self.redirect('/register?error=empty_fields')
        hashed_password = generate_password_hash(password)
        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT User_id FROM users WHERE Email=%s", (email,))
                if cursor.fetchone(): return self.redirect('/register?error=email_exists')
                cursor.execute("INSERT INTO users (Name, Email, Password) VALUES (%s, %s, %s)", (name, email, hashed_password))
            connection.commit()
            self.redirect('/login?success=registration_complete')
        finally:
            if connection: connection.close()
    
    def handle_logout(self):
        if "Cookie" in self.headers:
            cookie = cookies.SimpleCookie(self.headers["Cookie"])
            session_id_morsel = cookie.get("session_id")
            if session_id_morsel and session_id_morsel.value in sessions:
                del sessions[session_id_morsel.value]
        self.send_response(303)
        self.send_header('Set-Cookie', 'session_id=deleted; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT')
        self.send_header('Location', '/login')
        self.end_headers()

    def handle_profile(self, user_id):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        success_message = query_params.get('success', [None])[0]
        error_message = query_params.get('error', [None])[0]
        connection = connect_db()
        if not connection: return self.serve_template('profile.html', {'error_message': 'DB Error'})
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT User_id, Name, Email FROM users WHERE User_id = %s", (user_id,))
                user_data = cursor.fetchone()
                cursor.execute("SELECT m.Name AS movie_name, r.Rating_value AS stars FROM rating r JOIN movie m ON r.Movie_id = m.Movie_id WHERE r.User_id = %s ORDER BY r.Rating_id DESC LIMIT 5", (user_id,))
                user_ratings = cursor.fetchall()
                cursor.execute("SELECT m.Movie_id, m.Name, m.Poster_URL FROM watchlist w JOIN movie m ON w.Movie_id = m.Movie_id WHERE w.User_id = %s ORDER BY w.Date_added DESC", (user_id,))
                watchlist_movies = cursor.fetchall()
            context = {'user_data': user_data, 'user_ratings': user_ratings, 'watchlist_movies': watchlist_movies, 'success_message': success_message, 'error_message': error_message}
            self.serve_template('profile.html', context)
        finally:
            if connection: connection.close()

    def handle_update_profile(self, data):
        user_id = self.get_session_user()
        if not user_id: return self.redirect('/login')
        new_name = data.get('name', [''])[0].strip()
        new_password = data.get('new_password', [''])[0]
        if not new_name: return self.redirect('/profile?error=name_required')
        
        update_fields, params = ["Name = %s"], [new_name]
        if new_password:
            hashed_password = generate_password_hash(new_password)
            update_fields.append("Password = %s")
            params.append(hashed_password)
        params.append(user_id)
        
        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
                sql = f"UPDATE users SET {', '.join(update_fields)} WHERE User_id = %s"
                cursor.execute(sql, tuple(params))
            connection.commit()
            self.redirect('/profile?success=updated')
        except pymysql.MySQLError as e:
            print(f"Profile update error: {e}")
            self.redirect('/profile?error=update_failed')
        finally:
            if connection: connection.close()

    
    def handle_browse(self, user_id):
        MOVIES_PER_PAGE = 20
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        try: current_page = int(query_params.get('page', ['1'])[0])
        except ValueError: current_page = 1
        search_query = query_params.get('search_query', [''])[0]
        genre_filter = query_params.get('genre', [''])[0]
        
        conditions, params = [], []
        if search_query:
            conditions.append("m.Name LIKE %s")
            params.append(f"%{search_query}%")
        if genre_filter:
            conditions.append("m.Genre_id = %s")
            params.append(genre_filter)
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        connection = connect_db()
        if not connection: return self.serve_template('browser.html', {'error_message': 'DB Error'})
        try:
            with connection.cursor() as cursor:
                count_sql = f"SELECT COUNT(*) as total FROM movie m {where_clause}"
                cursor.execute(count_sql, tuple(params))
                total_movies = cursor.fetchone()['total']
                total_pages = math.ceil(total_movies / MOVIES_PER_PAGE)
                offset = (current_page - 1) * MOVIES_PER_PAGE
                movies_sql = f"SELECT m.Movie_id, m.Name, m.Release_year, m.Duration, m.Poster_URL, g.Title AS Genre, p.Platformname AS Platform FROM movie m JOIN genre g ON m.Genre_id = g.Genre_id JOIN platform p ON m.Platform_id = p.Platform_id {where_clause} ORDER BY m.Release_year DESC LIMIT %s OFFSET %s"
                final_params = tuple(params) + (MOVIES_PER_PAGE, offset)
                cursor.execute(movies_sql, final_params)
                movies_list = cursor.fetchall()
                cursor.execute("SELECT Genre_id, Title FROM genre ORDER BY Title")
                available_genres = cursor.fetchall()
            context = {'movies': movies_list, 'available_genres': available_genres, 'search_query': search_query, 'selected_genre': genre_filter, 'current_page': current_page, 'total_pages': total_pages}
            self.serve_template('browser.html', context)
        finally:
            if connection: connection.close()

    def handle_movie_details(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        movie_id_str = query_params.get('id', [None])[0]
        if not movie_id_str: return self.send_error(404, "Movie ID missing")
        try: movie_id = int(movie_id_str)
        except (ValueError, TypeError): return self.send_error(400, "Invalid Movie ID")

        connection = connect_db()
        if not connection: return self.serve_template('movie_details.html', {'error_message': 'DB Error'})
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT m.*, g.Title AS Genre, p.Platformname AS Platform FROM movie m LEFT JOIN genre g ON m.Genre_id = g.Genre_id LEFT JOIN platform p ON m.Platform_id = p.Platform_id WHERE m.Movie_id = %s", (movie_id,))
                movie_details = cursor.fetchone()
                similar_movies = []
                if movie_details:
                    cursor.execute("SELECT m.*, g.Title as Genre, p.Platformname as Platform FROM movie_similarity ms JOIN movie m ON m.Movie_id = ms.movie_id_2 LEFT JOIN genre g ON m.Genre_id = g.Genre_id LEFT JOIN platform p ON m.Platform_id = p.Platform_id WHERE ms.movie_id_1 = %s AND m.Movie_id != %s ORDER BY ms.similarity_score DESC LIMIT 4", (movie_id, movie_id))
                    similar_movies = cursor.fetchall()
            context = {'movie': movie_details, 'similar_movies': similar_movies}
            self.serve_template('movie_details.html', context)
        finally:
            if connection: connection.close()

    def handle_rating(self, data):
        user_id = self.get_session_user()
        if not user_id: self.send_response(401); self.end_headers(); return self.wfile.write(b'Unauthorized')
        try:
            movie_id = int(data.get('movie_id', [''])[0])
            rating_value = int(data.get('rating', [''])[0])
            if not (1 <= rating_value <= 5): raise ValueError()
        except (ValueError, IndexError):
            self.send_response(400); self.end_headers(); return self.wfile.write(b'Invalid data')
        
        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO rating (User_id, Movie_id, Rating_value) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE Rating_value = VALUES(Rating_value)"
                cursor.execute(sql, (user_id, movie_id, rating_value))
            connection.commit()
            self.send_response(200); self.send_header('Content-type', 'text/plain; charset=utf-8'); self.end_headers(); self.wfile.write(b'Success')
        except pymysql.MySQLError as e:
            print(f"Rating Error: {e}"); self.send_error(500, "DB Error")
        finally:
            if connection: connection.close()

    def handle_toggle_watchlist(self, data):
        user_id = self.get_session_user()
        if not user_id:
            self.send_response(401); self.send_header('Content-type', 'application/json'); self.end_headers()
            return self.wfile.write(json.dumps({'error': 'Not logged in'}).encode('utf-8'))
        try: movie_id = int(data.get('movie_id', [''])[0])
        except (ValueError, IndexError):
            self.send_response(400); self.send_header('Content-type', 'application/json'); self.end_headers()
            return self.wfile.write(json.dumps({'error': 'Invalid Movie ID'}).encode('utf-8'))
        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT Watchlist_id FROM watchlist WHERE User_id = %s AND Movie_id = %s", (user_id, movie_id))
                if cursor.fetchone():
                    cursor.execute("DELETE FROM watchlist WHERE User_id = %s AND Movie_id = %s", (user_id, movie_id))
                    response_data = {'status': 'removed'}
                else:
                    cursor.execute("INSERT INTO watchlist (User_id, Movie_id) VALUES (%s, %s)", (user_id, movie_id))
                    response_data = {'status': 'added'}
            connection.commit()
            self.send_response(200); self.send_header('Content-type', 'application/json'); self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
        finally:
            if connection: connection.close()

    def handle_recommend(self, data):
        user_id = self.get_session_user()
        if not user_id: return self.redirect('/login')
        movie_name = data.get('movie_name', [''])[0]
        algo_type = data.get('algo_type', [''])[0]
        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        
        recommendations = []
        try:
            with connection.cursor() as cursor:
                if algo_type == 'content':
                    cursor.execute("SELECT Movie_id FROM movie WHERE Name = %s", (movie_name,))
                    movie = cursor.fetchone()
                    if movie:
                        movie_id = movie['Movie_id']
                        cursor.execute("SELECT m.*, g.Title as Genre, p.Platformname as Platform FROM movie_similarity ms JOIN movie m ON m.Movie_id = ms.movie_id_2 JOIN genre g ON m.Genre_id = g.Genre_id JOIN platform p ON m.Platform_id = p.Platform_id WHERE ms.movie_id_1 = %s AND m.Movie_id != %s ORDER BY ms.similarity_score DESC LIMIT 10", (movie_id, movie_id))
                        recommendations = cursor.fetchall()
                
                elif algo_type == 'collaborative':
                    recommended_ids = self.get_collaborative_recommendations(user_id, connection)
                    if recommended_ids:
                        placeholders = ', '.join(['%s'] * len(recommended_ids))
                        sql_details = f"SELECT m.*, g.Title as Genre, p.Platformname as Platform FROM movie m JOIN genre g ON m.Genre_id = g.Genre_id JOIN platform p ON m.Platform_id = p.Platform_id WHERE m.Movie_id IN ({placeholders})"
                        cursor.execute(sql_details, recommended_ids)
                        all_movies = {movie['Movie_id']: movie for movie in cursor.fetchall()}
                        recommendations = [all_movies[rec_id] for rec_id in recommended_ids if rec_id in all_movies]
                
                elif algo_type == 'hybrid':
                    content_recs, collab_recs = [], []
                    cursor.execute("SELECT Movie_id FROM movie WHERE Name = %s", (movie_name,))
                    movie_data_hybrid = cursor.fetchone()
                    if movie_data_hybrid:
                        target_movie_id_hybrid = movie_data_hybrid['Movie_id']
                        cursor.execute("SELECT m.*, g.Title as Genre, p.Platformname as Platform FROM movie_similarity ms JOIN movie m ON m.Movie_id = ms.movie_id_2 JOIN genre g ON m.Genre_id = g.Genre_id JOIN platform p ON m.Platform_id = p.Platform_id WHERE ms.movie_id_1 = %s AND m.Movie_id != %s ORDER BY ms.similarity_score DESC LIMIT 5", (target_movie_id_hybrid, target_movie_id_hybrid))
                        content_recs = cursor.fetchall()
                    
                    collab_ids = self.get_collaborative_recommendations(user_id, connection)
                    if collab_ids:
                        placeholders = ', '.join(['%s'] * len(collab_ids))
                        sql_collab = f"SELECT m.*, g.Title as Genre, p.Platformname as Platform FROM movie m JOIN genre g ON m.Genre_id = g.Genre_id JOIN platform p ON m.Platform_id = p.Platform_id WHERE m.Movie_id IN ({placeholders})"
                        cursor.execute(sql_collab, collab_ids[:5])
                        all_collab_movies = {movie['Movie_id']: movie for movie in cursor.fetchall()}
                        collab_recs = [all_collab_movies[rec_id] for rec_id in collab_ids[:5] if rec_id in all_collab_movies]
                    
                    combined_recs = {}
                    for rec in content_recs + collab_recs:
                        if rec['Movie_id'] not in combined_recs: combined_recs[rec['Movie_id']] = rec
                    recommendations = list(combined_recs.values())

            self.serve_template('final.html', {'recommendations': recommendations})
        except Exception as e:
            print(f"An unexpected error occurred in handle_recommend: {e}")
            self.serve_template('final.html', {'recommendations': [], 'error_message': 'An unexpected error occurred.'})
        finally:
            if connection: connection.close()

    def get_collaborative_recommendations(self, target_user_id, connection):
        try:
            sql_query = "SELECT User_id, Movie_id, Rating_value FROM rating"
            df = pd.read_sql(sql_query, connection)
            if df.empty or target_user_id not in df['User_id'].unique(): return []
            
            user_movie_matrix = df.pivot_table(index='User_id', columns='Movie_id', values='Rating_value').fillna(0)
            user_similarity_df = pd.DataFrame(cosine_similarity(user_movie_matrix), index=user_movie_matrix.index, columns=user_movie_matrix.index)
            
            similar_users = user_similarity_df[target_user_id].sort_values(ascending=False).iloc[1:]
            if similar_users.empty: return []

            recommended_movies, final_recommendations = {}, {}
            for similar_user_id, similarity_score in similar_users.head(3).items():
                if similarity_score < 0.2: continue
                similar_user_ratings = user_movie_matrix.loc[similar_user_id]
                for movie_id, rating in similar_user_ratings[similar_user_ratings > 3].items():
                    if movie_id not in recommended_movies: recommended_movies[movie_id] = []
                    recommended_movies[movie_id].append(rating * similarity_score)
            
            watched_movie_ids = user_movie_matrix.loc[target_user_id][user_movie_matrix.loc[target_user_id] > 0].index
            for movie_id, scores in recommended_movies.items():
                if movie_id not in watched_movie_ids:
                    final_recommendations[movie_id] = sum(scores) / len(scores)

            sorted_recs = sorted(final_recommendations.items(), key=lambda item: item[1], reverse=True)
            return [movie_id for movie_id, score in sorted_recs[:10]]
        except Exception as e:
            print(f"Error in collaborative filtering: {e}")
            return []

    
    def handle_admin_page(self):
        if not self.is_admin():
            return self.send_error(403, 'Forbidden: Admins only')
        
        path_only = urllib.parse.urlparse(self.path).path
        if path_only == '/admin':
            self.serve_template('admin_dashboard.html')
        elif path_only == '/admin/movies':
            self.handle_admin_list_movies()
        elif path_only == '/admin/movie/add':
            self.handle_admin_movie_form()
        elif path_only == '/admin/movie/edit':
            self.handle_admin_movie_form_for_edit()
        elif path_only == '/admin/users':
            self.handle_admin_list_users()
        else:
            self.send_error(404, 'Admin Page Not Found')

    def handle_admin_post_requests(self, path_only, data):
        if not self.is_admin():
            return self.send_error(403, "Forbidden")
        
        admin_post_routes = {
            '/admin/movie/add': self.handle_admin_add_movie,
            '/admin/movie/edit': self.handle_admin_update_movie,
            '/admin/movie/delete': self.handle_admin_delete_movie,
            '/admin/user/toggle_admin': self.handle_admin_toggle_admin,
            '/admin/user/delete': self.handle_admin_delete_user,
        }
        handler = admin_post_routes.get(path_only)
        if path_only.startswith('/admin/movie/delete') or path_only.startswith('/admin/user/'):
            handler(None)
        elif handler:
            handler(data)
        else:
            self.send_error(404, "Admin POST path not found")

    def handle_admin_list_movies(self):
        connection = connect_db()
        if not connection: return self.serve_template('admin_movies.html', {'error_message': 'DB Error'})
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT m.Movie_id, m.Name, m.Release_year, g.Title as Genre FROM movie m LEFT JOIN genre g ON m.Genre_id = g.Genre_id ORDER BY m.Movie_id DESC")
                movies_list = cursor.fetchall()
            self.serve_template('admin_movies.html', {'movies': movies_list})
        finally:
            if connection: connection.close()

    def handle_admin_movie_form(self):
        connection = connect_db()
        if not connection: return self.serve_template('admin_movie_form.html', {'error_message': 'DB Error'})
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM genre ORDER BY Title")
                genres = cursor.fetchall()
                cursor.execute("SELECT * FROM platform ORDER BY Platformname")
                platforms = cursor.fetchall()
            self.serve_template('admin_movie_form.html', {'genres': genres, 'platforms': platforms, 'movie': {}})
        finally:
            if connection: connection.close()

    def handle_admin_add_movie(self, data):
        try:
            name = data.get('name', [''])[0]
            release_year = int(data.get('release_year', ['0'])[0])
            duration = int(data.get('duration', ['0'])[0])
            description = data.get('description', [''])[0]
            poster_url = data.get('poster_url', [''])[0]
            genre_id = int(data.get('genre_id', ['0'])[0])
            platform_id = int(data.get('platform_id', ['0'])[0])
        except (ValueError, IndexError):
            return self.send_error(400, "Invalid form data")
        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
                sql = "INSERT INTO movie (Name, Release_year, Duration, Description, Poster_URL, Genre_id, Platform_id) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (name, release_year, duration, description, poster_url, genre_id, platform_id))
            connection.commit()
            self.redirect('/admin/movies')
        except pymysql.MySQLError as e:
            print(f"Admin add movie error: {e}")
            self.send_error(500, "Error adding movie to database.")
        finally:
            if connection: connection.close()

    def handle_admin_movie_form_for_edit(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        movie_id_str = query_params.get('id', [None])[0]
        if not movie_id_str:
            return self.send_error(404, "Movie ID is missing for edit")
        connection = connect_db()
        if not connection: return self.serve_template('admin_movie_form.html', {'error_message': 'DB Error'})
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM movie WHERE Movie_id = %s", (movie_id_str,))
                movie_data = cursor.fetchone()
                cursor.execute("SELECT * FROM genre ORDER BY Title")
                genres = cursor.fetchall()
                cursor.execute("SELECT * FROM platform ORDER BY Platformname")
                platforms = cursor.fetchall()
            if not movie_data:
                return self.send_error(404, "Movie not found")
            self.serve_template('admin_movie_form.html', {'genres': genres, 'platforms': platforms, 'movie': movie_data})
        finally:
            if connection: connection.close()

    def handle_admin_update_movie(self, data):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        movie_id = query_params.get('id', [None])[0]
        if not movie_id:
            return self.send_error(400, "Missing movie ID for update")
        try:
            name = data.get('name', [''])[0]
            release_year = int(data.get('release_year', ['0'])[0])
            duration = int(data.get('duration', ['0'])[0])
            description = data.get('description', [''])[0]
            poster_url = data.get('poster_url', [''])[0]
            genre_id = int(data.get('genre_id', ['0'])[0])
            platform_id = int(data.get('platform_id', ['0'])[0])
        except (ValueError, IndexError):
            return self.send_error(400, "Invalid form data")
        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
                sql = "UPDATE movie SET Name = %s, Release_year = %s, Duration = %s, Description = %s, Poster_URL = %s, Genre_id = %s, Platform_id = %s WHERE Movie_id = %s"
                cursor.execute(sql, (name, release_year, duration, description, poster_url, genre_id, platform_id, movie_id))
            connection.commit()
            self.redirect('/admin/movies')
        except pymysql.MySQLError as e:
            print(f"Admin update movie error: {e}")
            self.send_error(500, "Error updating movie in database.")
        finally:
            if connection: connection.close()

    def handle_admin_delete_movie(self, data):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        movie_id = query_params.get('id', [None])[0]
        if not movie_id:
            return self.send_error(400, "Missing movie ID for delete")
        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
                sql = "DELETE FROM movie WHERE Movie_id = %s"
                cursor.execute(sql, (movie_id,))
            connection.commit()
            self.redirect('/admin/movies')
        except pymysql.MySQLError as e:
            print(f"Admin delete movie error: {e}")
            self.send_error(500, "Error deleting movie from database.")
        finally:
            if connection: connection.close()  

    def handle_admin_list_users(self):
        connection = connect_db()
        if not connection: return self.serve_template('admin_users.html', {'error_message': 'DB Error'})
        users_list = []
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT User_id, Name, Email, is_admin FROM users ORDER BY User_id ASC")
                users_list = cursor.fetchall()
            self.serve_template('admin_users.html', {'users': users_list})
        finally:
            if connection: connection.close()

    def handle_admin_toggle_admin(self, data):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        target_user_id = query_params.get('id', [None])[0]
        
        current_admin_id = self.get_session_user()

        
        if not target_user_id or int(target_user_id) == current_admin_id:
            return self.redirect('/admin/users?error=self_update_forbidden')

        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
                sql = "UPDATE users SET is_admin = NOT is_admin WHERE User_id = %s"
                cursor.execute(sql, (target_user_id,))
            connection.commit()
            self.redirect('/admin/users')
        except pymysql.MySQLError as e:
            print(f"Admin toggle admin error: {e}")
            self.send_error(500, "Error updating user permissions.")
        finally:
            if connection: connection.close()

    def handle_admin_delete_user(self, data):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        target_user_id = query_params.get('id', [None])[0]

        current_admin_id = self.get_session_user()

        
        if not target_user_id or int(target_user_id) == current_admin_id:
            return self.redirect('/admin/users?error=self_delete_forbidden')

        connection = connect_db()
        if not connection: return self.send_error(500, "DB Error")
        try:
            with connection.cursor() as cursor:
            
                sql = "DELETE FROM users WHERE User_id = %s"
                cursor.execute(sql, (target_user_id,))
            connection.commit()
            self.redirect('/admin/users')
        except pymysql.MySQLError as e:
            print(f"Admin delete user error: {e}")
            self.send_error(500, "Error deleting user.")
        finally:
            if connection: connection.close()

if __name__ == "__main__":
    if not os.path.exists('templates'):
        print("Error: 'templates' directory not found.")
        exit(1)
    
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, MyHandler)
    print(f"Server running on http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.server_close()