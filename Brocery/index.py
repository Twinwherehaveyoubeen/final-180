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

@app.route('/signup')
def signup():
    return render_template('signup.html')

# @app.route ('/signup', methods={'GET', 'POST'})
# def signup():
#     if request.method =='POST':
#         username = request.form['username']
#         email = request.form['email']
#         account_type = request.form['account_type']
#         password = generate_password_hash(request.form{'password'})

#         id existing:
#             flash("User already exist ")
#         return redirect

@app.route('/login')
def login():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)
