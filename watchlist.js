
document.addEventListener("DOMContentLoaded", function() {
    
    document.body.addEventListener('click', function(e) {
        
        if (e.target && e.target.matches('button.watchlist-btn')) {
            const button = e.target;
            const movieId = button.dataset.movieId;

            
            button.disabled = true;

            fetch('/toggle_watchlist', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    'movie_id': movieId
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'added') {
                    button.textContent = '✓ تمت الإضافة';
                    button.classList.add('active');
                } else if (data.status === 'removed') {
                    button.textContent = 'أضف للمشاهدة';
                    button.classList.remove('active');
                }
                
                button.disabled = false;
            })
            .catch(error => {
                console.error('Error:', error);
                button.textContent = 'خطأ';
                button.disabled = false;
            });
        }
    });
});