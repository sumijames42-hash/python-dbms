import sqlite3
import hashlib
from getpass import getpass
from datetime import datetime

DB_NAME = "inventory.db"

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def connect():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def setup_database():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'staff'))
        );

        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            unit_price REAL NOT NULL CHECK(unit_price >= 0),
            FOREIGN KEY (category_id) REFERENCES categories(category_id)
        );

        CREATE TABLE IF NOT EXISTS stock_transactions (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            change_quantity INTEGER NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products(product_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        """)

        # Demo accounts are created only if they do not already exist.
        conn.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", hash_password("admin123"), "admin")
        )
        conn.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, role) VALUES (?, ?, ?)",
            ("staff", hash_password("staff123"), "staff")
        )
        conn.execute(
            "INSERT OR IGNORE INTO categories(category_name) VALUES (?)", ("General",)
        )

def read_int(prompt, minimum=None):
    while True:
        try:
            value = int(input(prompt).strip())
            if minimum is not None and value < minimum:
                print(f"Enter a number greater than or equal to {minimum}.")
                continue
            return value
        except ValueError:
            print("Please enter a valid whole number.")

def read_float(prompt, minimum=None):
    while True:
        try:
            value = float(input(prompt).strip())
            if minimum is not None and value < minimum:
                print(f"Enter a number greater than or equal to {minimum}.")
                continue
            return value
        except ValueError:
            print("Please enter a valid number.")

def login():
    print("\n=== Inventory Management System ===")
    username = input("Username: ").strip()
    password = getpass("Password: ")
    with connect() as conn:
        user = conn.execute(
            "SELECT user_id, username, role FROM users WHERE username=? AND password_hash=?",
            (username, hash_password(password))
        ).fetchone()
    if user:
        print(f"\nLogin successful. Welcome, {user[1]} ({user[2]}).")
        return {"user_id": user[0], "username": user[1], "role": user[2]}
    print("Invalid username or password.")
    return None

def list_categories():
    with connect() as conn:
        rows = conn.execute(
            "SELECT category_id, category_name FROM categories ORDER BY category_name"
        ).fetchall()
    if not rows:
        print("No categories found.")
    else:
        print("\nCategories:")
        for row in rows:
            print(f"  {row[0]}. {row[1]}")
    return rows

def add_category():
    name = input("New category name: ").strip()
    if not name:
        print("Category name cannot be empty.")
        return
    try:
        with connect() as conn:
            conn.execute("INSERT INTO categories(category_name) VALUES (?)", (name,))
        print("Category added.")
    except sqlite3.IntegrityError:
        print("That category already exists.")

def add_product(user):
    name = input("Product name: ").strip()
    if not name:
        print("Product name cannot be empty.")
        return
    categories = list_categories()
    if not categories:
        print("Add a category first.")
        return
    category_id = read_int("Category ID: ", 1)
    if category_id not in [c[0] for c in categories]:
        print("Invalid category ID.")
        return
    quantity = read_int("Opening quantity: ", 0)
    price = read_float("Unit price: ", 0)
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO products(product_name, category_id, quantity, unit_price) VALUES (?, ?, ?, ?)",
                (name, category_id, quantity, price)
            )
            product_id = cur.lastrowid
            if quantity > 0:
                conn.execute(
                    """INSERT INTO stock_transactions
                    (product_id, change_quantity, note, created_at, user_id)
                    VALUES (?, ?, ?, ?, ?)""",
                    (product_id, quantity, "Opening stock", datetime.now().isoformat(timespec="seconds"), user["user_id"])
                )
        print("Product added successfully.")
    except sqlite3.IntegrityError as exc:
        print(f"Could not add product: {exc}")

def view_products():
    with connect() as conn:
        rows = conn.execute("""
            SELECT p.product_id, p.product_name, c.category_name,
                   p.quantity, p.unit_price, p.quantity * p.unit_price
            FROM products p
            JOIN categories c ON c.category_id = p.category_id
            ORDER BY p.product_id
        """).fetchall()
    if not rows:
        print("No products found.")
        return
    print("\nID | Product | Category | Qty | Unit Price | Stock Value")
    print("-" * 75)
    for r in rows:
        print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | ₹{r[4]:.2f} | ₹{r[5]:.2f}")

def update_product():
    view_products()
    product_id = read_int("\nProduct ID to update: ", 1)
    with connect() as conn:
        row = conn.execute(
            "SELECT product_name, category_id, quantity, unit_price FROM products WHERE product_id=?",
            (product_id,)
        ).fetchone()
    if not row:
        print("Product not found.")
        return
    print("Press Enter to keep the current value.")
    name = input(f"Product name [{row[0]}]: ").strip() or row[0]
    list_categories()
    category_text = input(f"Category ID [{row[1]}]: ").strip()
    category_id = row[1] if not category_text else int(category_text)
    quantity_text = input(f"Quantity [{row[2]}]: ").strip()
    quantity = row[2] if not quantity_text else int(quantity_text)
    price_text = input(f"Unit price [{row[3]}]: ").strip()
    price = row[3] if not price_text else float(price_text)
    if quantity < 0 or price < 0:
        print("Quantity and price cannot be negative.")
        return
    try:
        with connect() as conn:
            valid = conn.execute("SELECT 1 FROM categories WHERE category_id=?", (category_id,)).fetchone()
            if not valid:
                print("Invalid category ID.")
                return
            conn.execute(
                "UPDATE products SET product_name=?, category_id=?, quantity=?, unit_price=? WHERE product_id=?",
                (name, category_id, quantity, price, product_id)
            )
        print("Product updated.")
    except (ValueError, sqlite3.IntegrityError) as exc:
        print(f"Invalid input or update failed: {exc}")

def delete_product(user):
    if user["role"] != "admin":
        print("Only an admin can delete products.")
        return
    view_products()
    product_id = read_int("\nProduct ID to delete: ", 1)
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM products WHERE product_id=?", (product_id,)).fetchone()
        if not exists:
            print("Product not found.")
            return
        # Keep referential integrity by deleting transaction history first.
        conn.execute("DELETE FROM stock_transactions WHERE product_id=?", (product_id,))
        conn.execute("DELETE FROM products WHERE product_id=?", (product_id,))
    print("Product and its stock history deleted.")

def record_stock_change(user):
    view_products()
    product_id = read_int("\nProduct ID: ", 1)
    with connect() as conn:
        product = conn.execute(
            "SELECT quantity FROM products WHERE product_id=?", (product_id,)
        ).fetchone()
        if not product:
            print("Product not found.")
            return
        change = read_int("Quantity change (use negative number for stock-out): ")
        new_quantity = product[0] + change
        if new_quantity < 0:
            print("Stock-out exceeds available quantity.")
            return
        note = input("Note (e.g. purchase/sale/adjustment): ").strip() or "Stock update"
        conn.execute("UPDATE products SET quantity=? WHERE product_id=?", (new_quantity, product_id))
        conn.execute(
            """INSERT INTO stock_transactions
            (product_id, change_quantity, note, created_at, user_id)
            VALUES (?, ?, ?, ?, ?)""",
            (product_id, change, note, datetime.now().isoformat(timespec="seconds"), user["user_id"])
        )
    print(f"Stock updated. New quantity: {new_quantity}")

def view_transactions():
    with connect() as conn:
        rows = conn.execute("""
            SELECT t.transaction_id, p.product_name, t.change_quantity,
                   t.note, t.created_at, u.username
            FROM stock_transactions t
            JOIN products p ON p.product_id = t.product_id
            JOIN users u ON u.user_id = t.user_id
            ORDER BY t.transaction_id DESC
        """).fetchall()
    if not rows:
        print("No stock transactions found.")
        return
    print("\nTransaction ID | Product | Change | Note | Date/Time | User")
    print("-" * 100)
    for r in rows:
        print(f"{r[0]} | {r[1]} | {r[2]:+d} | {r[3]} | {r[4]} | {r[5]}")

def low_stock_report():
    threshold = read_int("Show products with quantity at or below: ", 0)
    with connect() as conn:
        rows = conn.execute("""
            SELECT product_id, product_name, quantity
            FROM products WHERE quantity <= ? ORDER BY quantity, product_name
        """, (threshold,)).fetchall()
    if not rows:
        print("No products match that low-stock threshold.")
        return
    print("\nLow-stock report:")
    for row in rows:
        print(f"ID {row[0]} - {row[1]}: {row[2]} left")

def register_user(user):
    if user["role"] != "admin":
        print("Only an admin can register new users.")
        return
    username = input("New username: ").strip()
    password = getpass("New password: ")
    role = input("Role (admin/staff): ").strip().lower()
    if not username or not password or role not in ("admin", "staff"):
        print("Enter a username, password, and valid role (admin/staff).")
        return
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO users(username, password_hash, role) VALUES (?, ?, ?)",
                (username, hash_password(password), role)
            )
        print("User registered.")
    except sqlite3.IntegrityError:
        print("That username is already in use.")

def main_menu(user):
    while True:
        print(f"""
--- Main Menu | Logged in: {user['username']} ({user['role']}) ---
1. Add product
2. View products
3. Update product
4. Record stock in/out
5. Low-stock report
6. View stock transaction history
7. Add category
8. Delete product (admin only)
9. Register user (admin only)
0. Logout
""")
        choice = input("Choose an option: ").strip()
        try:
            if choice == "1": add_product(user)
            elif choice == "2": view_products()
            elif choice == "3": update_product()
            elif choice == "4": record_stock_change(user)
            elif choice == "5": low_stock_report()
            elif choice == "6": view_transactions()
            elif choice == "7":
                if user["role"] == "admin": add_category()
                else: print("Only an admin can add categories.")
            elif choice == "8": delete_product(user)
            elif choice == "9": register_user(user)
            elif choice == "0":
                print("Logged out.")
                break
            else: print("Invalid option.")
        except (sqlite3.Error, ValueError) as exc:
            print(f"Operation failed: {exc}")

def main():
    setup_database()
    print("Database ready: inventory.db")
    while True:
        user = login()
        if user:
            main_menu(user)
            break
        again = input("Try again? (y/n): ").strip().lower()
        if again != "y":
            print("Exiting.")
            break

if __name__ == "__main__":
    main()
