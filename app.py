from flask import Flask, request, jsonify, render_template, redirect, flash
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Змініть на безпечний секретний ключ

# Ініціалізація бази даних
def init_db():
    conn = sqlite3.connect('fact_check_bot.db')
    with conn:
        conn.execute(''' 
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                email TEXT UNIQUE,
                telegram_id INTEGER UNIQUE
            )
        ''')
    return conn

@app.route('/register', methods=['POST'])
def register():
    data = request.form  # Змінено на request.form для отримання даних з HTML форми
    telegram_id = data.get('telegram_id')
    email = data.get('email')

    conn = sqlite3.connect('fact_check_bot.db')
    try:
        with conn:
            conn.execute('INSERT INTO users (telegram_id, email) VALUES (?, ?)', (telegram_id, email))
        flash('Користувача зареєстровано успішно')
        return redirect('/')  # Перенаправлення на головну сторінку
    except sqlite3.IntegrityError:
        flash('Користувач вже зареєстрований')
        return redirect('/')  # Перенаправлення на головну сторінку
    finally:
        conn.close()

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    init_db()
    app.run(port=5000)
