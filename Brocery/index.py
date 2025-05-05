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
    database="brocery"
)
cursor = conn.cursor(dictionary=True, buffered=True)

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

    if 'account_type' not in session or session['account_type'] not in ['Admin', 'Vendor']:
        flash("You don't have permission to add products.")
        return redirect(url_for('products'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']
        sizes = request.form['sizes']
        image = request.files['image']

        if image and image.filename != '':
            filename = secure_filename(image.filename)
            image.save(os.path.join('static/images', filename))
        else:
            filename = 'default.png'

        cursor.execute("""
            INSERT INTO Products (Title, Description, Price, Sizes, Images, Vendor_Id)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (title, description, price, sizes, filename, session['user_id']))
        conn.commit()

        flash("Product added successfully!")
        return redirect(url_for('products'))

    return render_template('add_product.html')

@app.route('/choose_vendor', methods=['GET', 'POST'])
def choose_vendor():
    if request.method == 'POST':
        vendor_id = request.form['vendor_id']
        session['vendor_id'] = vendor_id
        return redirect(url_for('chat_request'))
    return render_template('choose_vendor.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    sender_id = session.get('user_id')
    vendor_id = session.get('vendor_id')

    if not vendor_id:
        return redirect(url_for('choose_vendor'))

    cursor.execute("""
        SELECT * FROM ChatRequests 
        WHERE user_id = %s AND vendor_id = %s AND status = 'accepted'
    """, (sender_id, vendor_id))
    request_status = cursor.fetchone()

    if not request_status and session.get('account_type') == 'customer':
        flash("Your chat request hasn't been accepted yet.")
        return redirect(url_for('home'))

    if request.method == 'POST':
        message = request.form['message']
        cursor.execute("""
            INSERT INTO Messages (Sender_Id, Receiver_Id, Message_Text)
            VALUES (%s, %s, %s)
        """, (sender_id, vendor_id, message))
        conn.commit()

    cursor.execute("""
        SELECT m.*, u.User_Name AS sender_name
        FROM Messages m
        JOIN Users u ON m.Sender_Id = u.User_Id
        WHERE (m.Sender_Id = %s AND m.Receiver_Id = %s)
           OR (m.Sender_Id = %s AND m.Receiver_Id = %s)
        ORDER BY m.Sent_At ASC
    """, (sender_id, vendor_id, vendor_id, sender_id))
    messages = cursor.fetchall()

    return render_template('chat.html', messages=messages, vendor_id=vendor_id)

@app.route('/chat-request', methods=['POST'])
def chat_request():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    vendor_id = request.form['vendor_id']
    user_id = session['user_id']

    cursor.execute("INSERT INTO ChatRequests (user_id, vendor_id, status) VALUES (%s, %s, %s)", 
                   (user_id, vendor_id, 'pending'))
    conn.commit()

    flash("Chat request sent!")
    return redirect(url_for('home'))

@app.route('/vendor-chat-requests')
def vendor_chat_requests():
    if 'user_id' not in session or session['account_type'] != 'vendor':
        return redirect(url_for('login'))

    vendor_id = session['user_id']
    cursor.execute("""
        SELECT cr.id, u.User_Name AS requester_name
        FROM ChatRequests cr
        JOIN Users u ON cr.user_id = u.User_Id
        WHERE cr.vendor_id = %s AND cr.status = 'pending'
    """, (vendor_id,))
    requests = cursor.fetchall()

    return render_template('vendor_chat_requests.html', requests=requests)

@app.route('/accept-chat', methods=['POST'])
def accept_chat():
    request_id = request.form['request_id']
    
    cursor.execute("UPDATE ChatRequests SET status = 'accepted' WHERE id = %s", (request_id,))
    conn.commit()

    return redirect(url_for('chat'))

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    cursor.execute("SELECT * FROM Products WHERE Product_Id = %s", (product_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found.")
        return redirect(url_for('products'))

    sizes = product['Sizes'].split(',') if product['Sizes'] else []

    cursor.execute("""
        SELECT r.Rating, r.Review_Text, r.Created_At, u.User_Name
        FROM Reviews r
        JOIN Users u ON r.User_Id = u.User_Id
        WHERE r.Product_Id = %s
        ORDER BY r.Created_At DESC
    """, (product_id,))
    reviews = cursor.fetchall()

    return render_template("product_details.html", product=product, reviews=reviews, sizes=sizes)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    product_id = request.form['product_id']
    size = request.form['size']
    quantity = int(request.form['quantity'])

    cursor.execute("""
        INSERT INTO Cart (User_Id, Product_Id, Size, Quantity)
        VALUES (%s, %s, %s, %s)
    """, (user_id, product_id, size, quantity))
    conn.commit()

    flash("Product added to cart!")
    return redirect(url_for('products'))

@app.route('/cart')
def view_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cursor.execute("""
        SELECT c.*, p.Title, p.Images, p.Price
        FROM Cart c
        JOIN Products p ON c.Product_Id = p.Product_Id
        WHERE c.User_Id = %s
    """, (user_id,))
    cart_items = cursor.fetchall()

    total_price = sum(item['Price'] * item['Quantity'] for item in cart_items)

    return render_template('cart.html', cart_items=cart_items, total=total_price)

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    if request.method == 'POST':
        cursor.execute("SELECT * FROM Cart WHERE User_Id = %s", (user_id,))
        cart_items = cursor.fetchall()

        if not cart_items:
            flash("Cart is empty.")
            return redirect(url_for('cart'))

        cursor.execute("INSERT INTO Orders (User_Id) VALUES (%s)", (user_id,))
        order_id = cursor.lastrowid

        for item in cart_items:
            cursor.execute("""
                INSERT INTO OrderItems (Order_Id, Product_Id, Size, Quantity)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item['Product_Id'], item['Size'], item['Quantity']))

        cursor.execute("DELETE FROM Cart WHERE User_Id = %s", (user_id,))
        conn.commit()

        flash("Order placed successfully!")
        return redirect(url_for('my_orders'))

    return render_template('checkout.html')

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    product_id = request.form['product_id']
    size = request.form['size']

    cursor.execute("""
        DELETE FROM Cart 
        WHERE User_Id = %s AND Product_Id = %s AND Size = %s
    """, (user_id, product_id, size))
    conn.commit()

    flash("Item removed from cart.")
    return redirect(url_for('view_cart'))


if __name__ == '__main__':
    app.run(debug=True)
