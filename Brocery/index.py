from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'


conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="cset155",
    database="shopping"
)
cursor = conn.cursor(dictionary=True)


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        account_type = request.form['account_type']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        cursor.execute("SELECT MAX(User_Id) + 1 AS NextId FROM Users")
        result = cursor.fetchone()
        user_id = result['NextId'] if result['NextId'] is not None else 1

        cursor.execute("""
            INSERT INTO Users (User_Id, User_Name, Account_Type, Email, Password)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, username, account_type, email, password))
        conn.commit()

        flash("Account created successfully!")
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password_input = request.form['password']

        cursor.execute("SELECT * FROM Users WHERE User_Name = %s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['Password'], password_input):
            session['username'] = user['User_Name']
            session['account_type'] = user['Account_Type']
            flash("Login successful!")
            return redirect(url_for('home'))
        else:
            flash("Invalid username or password.")

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/products')
def products():
    return render_template('products.html')


@app.route('/chat')
def chat():
    return render_template('chat.html')


if __name__ == '__main__':
    app.run(debug=True)
