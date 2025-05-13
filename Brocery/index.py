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
    database="store",
    ssl_disabled=True
)
cursor = conn.cursor(dictionary=True, buffered=True)

@app.route('/')
def home():
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT User_Id FROM Users WHERE Account_Type = 'Admin' LIMIT 1")
    admin = cursor.fetchone()
    admin_id = admin['User_Id'] if admin else None

    return render_template('home.html', admin_id=admin_id)


#Lets users create an account.
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
    #Lets users log in.
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cursor.execute("SELECT * FROM Users WHERE User_Name = %s", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user['Password'], password):
            session['username'] = user['User_Name']
            session['account_type'] = user['Account_Type']
            session['user_id'] = user['User_Id']
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))

    return render_template('login.html')

#Logs users out.
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))
#shows all of the filters by catagory 
@app.route('/products')
def products():
    category = request.args.get('category')
    if category:
        cursor.execute("SELECT * FROM Products WHERE Category = %s", (category,))
    else:
        cursor.execute("SELECT * FROM Products")
    products = cursor.fetchall()
    return render_template('products.html', products=products)


#allows the vendor and the admin to add products that they want 
@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        price = request.form['price']
        sizes = request.form['sizes']
        category = request.form['category']
        image = request.files['image']

        filename = secure_filename(image.filename)
        image.save(os.path.join('static/images', filename))

        cursor.execute("""
            INSERT INTO Products (Title, Description, Images, Price, Sizes, Category, Vendor_Id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (title, description, filename, price, sizes, category, session['user_id']))
        conn.commit()

        flash('Product added successfully!', 'success')
        return redirect(url_for('products'))

    return render_template('add_product.html')
#that the costomer can choose what vendor they want to chat with 
@app.route('/choose_vendor', methods=['GET', 'POST'])
def choose_vendor():
    if request.method == 'POST':
        vendor_id = request.form['vendor_id']
        return redirect(url_for('chat_with_vendor', receiver_id=vendor_id))

    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT User_Id, User_Name FROM Users WHERE Account_Type = 'Vendor'")
    vendors = cursor.fetchall()

    cursor.execute("SELECT User_Id FROM Users WHERE Account_Type = 'Admin' LIMIT 1")
    admin = cursor.fetchone()
    admin_id = admin['User_Id'] if admin else None

    return render_template('choose_vendor.html', vendors=vendors, admin_id=admin_id)
    


#the chat between the vendor and the customer 
@app.route('/chat/<int:receiver_id>', methods=['GET', 'POST'])
def chat_with_vendor(receiver_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    sender_id = session['user_id']

    if request.method == 'POST':
        message = request.form['message']
        cursor.execute("""
            INSERT INTO Messages (Sender_Id, Receiver_Id, Content)
            VALUES (%s, %s, %s)
        """, (sender_id, receiver_id, message))
        conn.commit()
        return redirect(url_for('chat_with_vendor', receiver_id=receiver_id))

    cursor.execute("""
        SELECT 
            m.Content, m.Sent_At,
            sender.User_Name AS Sender_Name,
            receiver.User_Name AS Receiver_Name
        FROM Messages m
        JOIN Users sender ON m.Sender_Id = sender.User_Id
        JOIN Users receiver ON m.Receiver_Id = receiver.User_Id
        WHERE (m.Sender_Id = %s AND m.Receiver_Id = %s)
           OR (m.Sender_Id = %s AND m.Receiver_Id = %s)
        ORDER BY m.Sent_At ASC
    """, (sender_id, receiver_id, receiver_id, sender_id))
    messages = cursor.fetchall()

    return render_template('chat_vendor.html', messages=messages, receiver_id=receiver_id)



#the vendor can see who messaged them 
@app.route('/vendor_chats')
def vendor_chats():
    if 'user_id' not in session or session['account_type'] != 'Vendor':
        return redirect(url_for('login'))

    vendor_id = session['user_id']
    cursor.execute("""
        SELECT DISTINCT Sender_Id, Users.User_Name
        FROM TempChat
        JOIN Users ON Users.User_Id = TempChat.Sender_Id
        WHERE Receiver_Id = %s
    """, (vendor_id,))
    customers = cursor.fetchall()
    return render_template('vendor_chats.html', customers=customers)

#the customers can send chat request forms to chat with them
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
#vendor see pending chat request that the customers sent them 
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
#that the vendors accepted the customers chat request 
@app.route('/accept-chat', methods=['POST'])
def accept_chat():
    request_id = request.form['request_id']
    
    cursor.execute("UPDATE ChatRequests SET status = 'accepted' WHERE id = %s", (request_id,))
    conn.commit()

    return redirect(url_for('chat'))

#main chat between any two users
@app.route('/chat/<int:receiver_id>', methods=['GET', 'POST'])
def chat(receiver_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    sender_id = session['user_id']

    if request.method == 'POST':
        message = request.form['message']
        cursor.execute(
            "INSERT INTO Messages (Sender_Id, Receiver_Id, Content) VALUES (%s, %s, %s)",
            (sender_id, receiver_id, message)
        )
        conn.commit()
        return redirect(url_for('chat', receiver_id=receiver_id))

    cursor.execute("""
        SELECT m.*, u.User_Name as SenderName
        FROM Messages m
        JOIN Users u ON m.Sender_Id = u.User_Id
        WHERE (Sender_Id = %s AND Receiver_Id = %s)
           OR (Sender_Id = %s AND Receiver_Id = %s)
        ORDER BY m.Sent_At ASC
    """, (sender_id, receiver_id, receiver_id, sender_id))
    messages = cursor.fetchall()

  
    cursor.execute("SELECT User_Name FROM Users WHERE User_Id = %s", (receiver_id,))
    receiver = cursor.fetchone()

    return render_template('chat.html', messages=messages, receiver=receiver)

#shows the product deltails 
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    cursor.execute("""
        SELECT p.*, u.User_Name 
        FROM Products p 
        JOIN Users u ON p.Vendor_Id = u.User_Id 
        WHERE p.Product_Id = %s
    """, (product_id,))
    product = cursor.fetchone()

    sizes = product['Sizes'].split(',') if product.get('Sizes') else []

    cursor.execute("SELECT * FROM Reviews WHERE Product_Id = %s", (product_id,))
    reviews = cursor.fetchall()

    return render_template('product_detail.html', product=product, sizes=sizes, reviews=reviews)

#adds product to users cart
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
#desplays cart with the price of the items 
@app.route('/cart')
def cart():
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

#places the order and clears the cart 
@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    if request.method == 'POST':
        card_number = request.form['card_number']
        expiry = request.form['expiry']
        cvv = request.form['cvv']
        home_address = request.form['home_address']

        
        cursor.execute("SELECT * FROM Cart WHERE User_Id = %s", (user_id,))
        cart_items = cursor.fetchall()

        if not cart_items:
            flash('Your cart is empty.', 'warning')
            return redirect(url_for('checkout'))

     
        cursor.execute("INSERT INTO Orders (User_Id, Status, Created_At) VALUES (%s, %s, NOW())",
               (user_id, 'Pending'))
        order_id = cursor.lastrowid

   
        for item in cart_items:
            cursor.execute("""
                INSERT INTO Order_Items (Order_Id, Product_Id, Size, Quantity)
                VALUES (%s, %s, %s, %s)
            """, (order_id, item['Product_Id'], item['Size'], item['Quantity']))

        cursor.execute("DELETE FROM Cart WHERE User_Id = %s", (user_id,))

        conn.commit()

        flash('Order placed successfully!', 'success')
        return redirect(url_for('payment_success'))

    
    cursor.execute("SELECT * FROM Cart WHERE User_Id = %s", (user_id,))
    cart_items = cursor.fetchall()

    cursor.execute("SELECT * FROM Addresses WHERE User_Id = %s", (user_id,))
    addresses = cursor.fetchall()

    return render_template('checkout.html', cart_items=cart_items, addresses=addresses)

#removes the items that you dont want in the cart 
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
    return redirect(url_for('cart'))

#shows the customers orders and the last order they had
@app.route('/myorders')
def my_orders():
    user_id = session.get('user_id')

   
    cursor.execute("SELECT * FROM Orders WHERE User_Id = %s", (user_id,))
    orders = cursor.fetchall()

    for order in orders:
        cursor.execute("""
            SELECT oi.Product_Id, oi.Size, oi.Quantity,
                   p.Title, p.Images
            FROM Order_Items oi
            JOIN Products p ON oi.Product_Id = p.Product_Id
            WHERE oi.Order_Id = %s
        """, (order['Order_Id'],))
        items = cursor.fetchall()
        order['items_list'] = items

    return render_template('my_orders.html', orders=orders)

# Shows all orders containing products from the logged-in vendor.
@app.route('/vendororders')
def vendor_orders():
    if 'user_id' not in session or session['account_type'] != 'vendor':
        return redirect(url_for('login'))

    vendor_id = session['user_id']
    cursor.execute("""
        SELECT o.Order_Id, o.Created_At, oi.*, p.Title, p.Images
        FROM Orders o
        JOIN OrderItems oi ON o.Order_Id = oi.Order_Id
        JOIN Products p ON oi.Product_Id = p.Product_Id
        WHERE p.Vendor_Id = %s
        ORDER BY o.Created_At DESC
    """, (vendor_id,))
    orders = cursor.fetchall()
    return render_template('vendor_orders.html', orders=orders)

#admin and vendor can see the complaints that the customer had 
@app.route('/complaints')
def complaint_list():
    if 'username' not in session:
        return redirect('/login')

    if session.get('account_type') not in ['Vendor', 'Admin']:
        return "Unauthorized access", 403

    cursor.execute("""
        SELECT c.Complaint_Id, c.Title, c.Description, c.Status, c.Date,
               c.Product_Id, c.Order_Id, u.User_Name
        FROM Complaints c
        JOIN Users u ON c.User_Id = u.User_Id
        ORDER BY c.Date DESC
    """)
    complaints = cursor.fetchall()
    return render_template('complaint_list.html', complaints=complaints)

# theat the customer logged in can complain about the product
@app.route('/complaint', methods=['GET', 'POST'])
def complaint():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        order_id = request.form['order_id']       
        product_id = request.form['product_id']     
        user_id = session['user_id']

        cursor.execute("""
            INSERT INTO Complaints (User_Id, Order_Id, Title, Description, Product_Id)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, order_id, title, description, product_id))
        conn.commit()
        flash("Complaint submitted successfully.", "success")
        return redirect(url_for('products'))

    return render_template('complaint.html')
#shows the profile information of the customer
@app.route('/account')
def account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cursor.execute("SELECT * FROM Users WHERE User_Id = %s", (user_id,))
    user = cursor.fetchone()
    return render_template('account.html', user=user)

#that the admin can see all of the accounts made. 
@app.route('/accounts')
def accounts():
    if 'user_id' not in session or session['account_type'] != 'Admin':
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM Users")
    users = cursor.fetchall()
    return render_template('accounts.html', users=users)

#that only the person who made the item can edit it
@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'account_type' not in session or session['account_type'] not in ['Admin', 'Vendor']:
        flash("You don't have permission to edit products.")
        return redirect(url_for('products'))

    cursor.execute("SELECT * FROM Products WHERE Product_Id = %s", (product_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found.")
        return redirect(url_for('products'))

    if session['account_type'] == 'Vendor' and product['Vendor_Id'] != session['user_id']:
        flash("You can only edit your own products.")
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
            filename = product['Images']  

        cursor.execute("""
            UPDATE Products
            SET Title = %s, Description = %s, Price = %s, Sizes = %s, Images = %s
            WHERE Product_Id = %s
        """, (title, description, price, sizes, filename, product_id))
        conn.commit()

        flash("Product updated successfully!")
        return redirect(url_for('products'))

    return render_template('edit_product.html', product=product)

#that the vendor and the admin can veiw the customer order 
@app.route('/customer_orders')
def customer_orders():
    if 'user_id' not in session or session.get('account_type') not in ['Vendor', 'Admin']:
        return redirect(url_for('login'))  

    cursor.execute("""
        SELECT 
            Orders.Order_Id, Orders.Created_At, Orders.Status, 
            Users.User_Name, 
            Products.Title, Products.Images, 
            OrderItems.Size, OrderItems.Quantity
        FROM Orders
        JOIN Users ON Orders.User_Id = Users.User_Id
        JOIN OrderItems ON Orders.Order_Id = OrderItems.Order_Id
        JOIN Products ON OrderItems.Product_Id = Products.Product_Id
        ORDER BY Orders.Order_Id DESC
    """)
    results = cursor.fetchall()

    orders = {}
    for row in results:
        order_id = row['Order_Id']
        if order_id not in orders:
            orders[order_id] = {
                'Order_Id': order_id,
                'Created_At': row['Created_At'],
                'Status': row['Status'],
                'User_Name': row['User_Name'],
                'items_list': []
            }
        orders[order_id]['items_list'].append({
            'Title': row['Title'],
            'Images': row['Images'],
            'Size': row['Size'],
            'Quantity': row['Quantity']
        })

    return render_template('customer_orders.html', orders=orders.values())

#that the aadmin dashboard page 
@app.route('/admin')
def admin_dashboard():
    if 'username' not in session or session['account_type'] != 'Admin':
        return redirect(url_for('login'))  
    return render_template('admin_dashboard.html')

#shows the custoners saved address
@app.route('/saved_addresses')
def saved_addresses():
    if 'username' not in session or session['account_type'] != 'Customer':
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM Addresses WHERE User_Id = %s", (session['user_id'],))
    addresses = cursor.fetchall()
    return render_template('saved_addresses.html', addresses=addresses)

#sends a review for the product 
@app.route('/review/<int:product_id>', methods=['POST'])
def submit_review(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    rating = int(request.form['rating'])
    review_text = request.form['review_text']
    user_id = session['user_id']

    cursor.execute("""
        INSERT INTO Reviews (Product_Id, User_Id, Rating, Review_Text)
        VALUES (%s, %s, %s, %s)
    """, (product_id, user_id, rating, review_text))
    conn.commit()

    return redirect(url_for('product_detail', product_id=product_id))

#Adminand the vendor deletes a product and related data
@app.route('/delete_product/<int:product_id>')
def delete_product(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor.execute("SELECT Vendor_Id FROM Products WHERE Product_Id = %s", (product_id,))
    product = cursor.fetchone()

    if not product:
        flash("Product not found.")
        return redirect(url_for('products'))

    if session['account_type'] == 'Admin' or (session['account_type'] == 'Vendor' and product['Vendor_Id'] == session['user_id']):
        cursor.execute("DELETE FROM Order_Items WHERE Product_Id = %s", (product_id,))
        cursor.execute("DELETE FROM Cart WHERE Product_Id = %s", (product_id,))
        cursor.execute("DELETE FROM Reviews WHERE Product_Id = %s", (product_id,))

        cursor.execute("DELETE FROM Products WHERE Product_Id = %s", (product_id,))
        conn.commit()
        flash("Product deleted successfully.")
    else:
        flash("Unauthorized action.")

    return redirect(url_for('products'))

#lets the admin and the vendor change the order status of the item 
@app.route('/update_order_status', methods=['POST'])
def update_order_status():
    order_id = request.form['order_id']
    new_status = request.form['status'].strip() 

    print(f"Updating Order ID {order_id} to status '{new_status}'")  

    cursor.execute("UPDATE Orders SET Status = %s WHERE Order_Id = %s", (new_status, order_id))
    conn.commit()
    return redirect(url_for('customer_orders'))


#lets the admin and the user update the complaint status 
@app.route('/update_complaint_status', methods=['POST'])
def update_complaint_status():
    if 'user_id' not in session or session['account_type'] not in ['Admin', 'Vendor']:
        return redirect(url_for('login'))

    complaint_id = request.form['complaint_id']
    new_status = request.form['status']

    cursor.execute("UPDATE Complaints SET Status = %s WHERE Complaint_Id = %s", (new_status, complaint_id))
    conn.commit()

    return redirect(url_for('complaint_list'))

#shows the customers saved addresses 
@app.route('/saved_addresses', methods=['GET'])
def show_saved_addresses():
    user_id = session.get('user_id')
    cursor.execute("SELECT * FROM Addresses WHERE User_Id = %s", (user_id,))
    addresses = cursor.fetchall()
    return render_template('saved_addresses.html', addresses=addresses)


#it lets the customer add his or hers adresses 
@app.route('/add_address', methods=['POST'])
def add_address():
    user_id = session.get('user_id')
    address = request.form['address']
    is_default = request.form.get('is_default', False)
    if is_default:
        cursor.execute("UPDATE Addresses SET Is_Default = 0 WHERE User_Id = %s", (user_id,))
    cursor.execute("INSERT INTO Addresses (User_Id, Address, Is_Default) VALUES (%s, %s, %s)", (user_id, address, is_default))
    conn.commit()
    return redirect(url_for('show_saved_addresses'))

#allows the customer deleted the address that was added
@app.route('/delete_address/<int:address_id>')
def delete_address(address_id):
    cursor.execute("DELETE FROM Addresses WHERE Address_Id = %s", (address_id,))
    conn.commit()
    return redirect(url_for('show_saved_addresses'))

#sets the cusotmers address as the default one
@app.route('/set_default_address/<int:address_id>')
def set_default_address(address_id):
    user_id = session.get('user_id')
    cursor.execute("UPDATE Addresses SET Is_Default = 0 WHERE User_Id = %s", (user_id,))
    cursor.execute("UPDATE Addresses SET Is_Default = 1 WHERE Address_Id = %s", (address_id,))
    conn.commit()
    return redirect(url_for('show_saved_addresses'))

#shows a payment success page
@app.route('/payment_success')
def payment_success():
    return render_template('payment.html')


#admin can view all of the chats 
@app.route('/admin_view_chats')
def admin_view_chats():
    if 'user_id' not in session or session.get('account_type') != 'Admin':
        return redirect(url_for('login'))

    cursor.execute("""
        SELECT 
            m.Message_Id, m.Content, m.Sent_At,
            sender.User_Name AS Sender_Name,
            receiver.User_Name AS Receiver_Name
        FROM Messages m
        JOIN Users sender ON m.Sender_Id = sender.User_Id
        JOIN Users receiver ON m.Receiver_Id = receiver.User_Id
        ORDER BY m.Sent_At DESC
    """)
    messages = cursor.fetchall()

    return render_template('admin_chats.html', messages=messages)

#the admin can talk to people 
@app.route('/admin_chats_interactive', methods=['GET', 'POST'])
def admin_chats_interactive():
    if 'user_id' not in session or session.get('account_type') != 'Admin':
        return redirect(url_for('login'))

    admin_id = session['user_id']

    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT DISTINCT 
            LEAST(Sender_Id, Receiver_Id) AS user1,
            GREATEST(Sender_Id, Receiver_Id) AS user2
        FROM Messages
        WHERE Sender_Id != Receiver_Id
    """)
    pairs = cursor.fetchall()

    chat_threads = []

    for pair in pairs:
        user1 = pair['user1']
        user2 = pair['user2']

        cursor.execute("""
            SELECT 
                m.Content, m.Sent_At,
                sender.User_Name AS Sender_Name,
                m.Sender_Id, m.Receiver_Id
            FROM Messages m
            JOIN Users sender ON m.Sender_Id = sender.User_Id
            WHERE (m.Sender_Id = %s AND m.Receiver_Id = %s)
               OR (m.Sender_Id = %s AND m.Receiver_Id = %s)
            ORDER BY m.Sent_At ASC
        """, (user1, user2, user2, user1))
        messages = cursor.fetchall()

        if messages:
            cursor.execute("SELECT User_Name FROM Users WHERE User_Id = %s", (user1,))
            user1_name = cursor.fetchone()['User_Name']

            cursor.execute("SELECT User_Name FROM Users WHERE User_Id = %s", (user2,))
            user2_name = cursor.fetchone()['User_Name']

            chat_threads.append({
                'sender_id': user1,
                'receiver_id': user2,
                'sender_name': user1_name,
                'receiver_name': user2_name,
                'messages': messages
            })

    return render_template('admin_chats_interactive.html', chat_threads=chat_threads, admin_id=admin_id)


@app.route('/admin_send_message', methods=['POST'])
def admin_send_message():
    if 'user_id' not in session or session.get('account_type') != 'Admin':
        return redirect(url_for('login'))

    sender_id = session['user_id']
    receiver_id = request.form['receiver_id']
    message = request.form['message']

    cursor.execute("""
        INSERT INTO Messages (Sender_Id, Receiver_Id, Content)
        VALUES (%s, %s, %s)
    """, (sender_id, receiver_id, message))
    conn.commit()

    return redirect(url_for('admin_chats_interactive'))



if __name__ == '__main__':
    app.run(debug=True)


