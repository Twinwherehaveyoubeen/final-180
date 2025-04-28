import os
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key'


if not os.path.exists('static/images'):
    os.makedirs('static/images')


conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="cset155",
    database="shopping"
)
cursor = conn.cursor(dictionary=True, buffered=True)

@app.before_request
def dummy_login():
    session['user_id'] = 1

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
        return redirect(url_for('home'))

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
            session['user_id'] = user['User_Id']
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
    cursor.execute("SELECT * FROM Products")
    products = cursor.fetchall()
    return render_template('products.html', products=products)

@app.route('/addproduct', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']
        image = request.files['image']

        if image:
            filename = secure_filename(image.filename)
            image_path = os.path.join('static/images', filename)
            image.save(image_path)

            cursor.execute("""
                INSERT INTO Products (Title, Description, Price, Images, Vendor_Id)
                VALUES (%s, %s, %s, %s, %s)
            """, (title, description, price, filename, session['user_id']))  
            conn.commit()

            flash('Product added successfully!', 'success')
            return redirect(url_for('products'))

    return render_template('add_product.html')

@app.route('/choose_vendor', methods=['GET', 'POST'])
def choose_vendor():
    if request.method == 'POST':
        vendor_id = request.form['vendor_id']
        session['vendor_id'] = vendor_id
        return redirect(url_for('chat'))
    return render_template('choose_vendor.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    sender_id = session.get('user_id')
    vendor_id = session.get('vendor_id')

    if not vendor_id:
        return redirect(url_for('choose_vendor'))

    if request.method == 'POST':
        message = request.form['message']
        cursor.execute(
            "INSERT INTO Messages (Sender_Id, Receiver_Id, Message_Text) VALUES (%s, %s, %s)",
            (sender_id, vendor_id, message)
        )
        conn.commit()

    cursor.execute(
        """
        SELECT * FROM Messages
        WHERE (Sender_Id = %s AND Receiver_Id = %s)
           OR (Sender_Id = %s AND Receiver_Id = %s)
        ORDER BY Sent_At ASC
        """,
        (sender_id, vendor_id, vendor_id, sender_id)
    )
    messages = cursor.fetchall()

    return render_template('chat.html', messages=messages, vendor_id=vendor_id)

if __name__ == '__main__':
    app.run(debug=True)
