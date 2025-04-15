from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector

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

if __name__ == '__main__':
    app.run(debug=True)
