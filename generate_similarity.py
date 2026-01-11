import pymysql
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

def connect_db():
    return pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='movie',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

def get_movies():
    connection = connect_db()
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT Movie_id, Name, Description
            FROM movie
        """)
        movies = cursor.fetchall()
    connection.close()
    return movies

def calculate_similarity(movies):
    movie_ids = [movie['Movie_id'] for movie in movies]
    descriptions = [movie['Description'] if movie['Description'] else '' for movie in movies]
    
    tfidf = TfidfVectorizer()
    tfidf_matrix = tfidf.fit_transform(descriptions)
    similarity_matrix = cosine_similarity(tfidf_matrix)

    return movie_ids, similarity_matrix

def save_similarity(movie_ids, similarity_matrix):
    connection = connect_db()
    with connection.cursor() as cursor:
        
        cursor.execute("TRUNCATE TABLE movie_similarity")
        
        
        insert_queries = []
        for i in range(len(movie_ids)):
            for j in range(i + 1, len(movie_ids)):
                movie_id_1 = movie_ids[i]
                movie_id_2 = movie_ids[j]
                similarity_score = similarity_matrix[i][j]

                if similarity_score > 0.05:
                    insert_queries.append((movie_id_1, movie_id_2, similarity_score))

        if insert_queries:
            cursor.executemany("""
                INSERT INTO movie_similarity (movie_id_1, movie_id_2, similarity_score)
                VALUES (%s, %s, %s)
            """, insert_queries)
        
        connection.commit()
    connection.close()

def generate_movie_similarity():
    print("Extracting movie data...")
    movies = get_movies()
    print("Calculating similarities based on plot descriptions...")
    movie_ids, similarity_matrix = calculate_similarity(movies)
    print("Saving new similarity data...")
    save_similarity(movie_ids, similarity_matrix)
    print("Similarity data generated and saved successfully.")

if __name__ == "__main__":
    generate_movie_similarity()