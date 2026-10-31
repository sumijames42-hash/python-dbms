1import sqlite3
import hashlib
from getpass import getpass
from datetime import datetime

DB_NAME = "movie_booking.db"

def password_hash(password):
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
            role TEXT NOT NULL CHECK(role IN ('admin', 'customer'))
        );

        CREATE TABLE IF NOT EXISTS movies (
            movie_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            genre TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL CHECK(duration_minutes > 0),
            language TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1))
        );

        CREATE TABLE IF NOT EXISTS shows (
            show_id INTEGER PRIMARY KEY AUTOINCREMENT,
            movie_id INTEGER NOT NULL,
            show_date TEXT NOT NULL,
            show_time TEXT NOT NULL,
            screen_name TEXT NOT NULL,
            ticket_price REAL NOT NULL CHECK(ticket_price >= 0),
            total_seats INTEGER NOT NULL CHECK(total_seats > 0),
            FOREIGN KEY(movie_id) REFERENCES movies(movie_id)
        );

        CREATE TABLE IF NOT EXISTS bookings (
            booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            show_id INTEGER NOT NULL,
            seat_count INTEGER NOT NULL CHECK(seat_count > 0),
            total_amount REAL NOT NULL CHECK(total_amount >= 0),
            status TEXT NOT NULL DEFAULT 'BOOKED' CHECK(status IN ('BOOKED', 'CANCELLED')),
            booked_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(show_id) REFERENCES shows(show_id)
        );

        CREATE TABLE IF NOT EXISTS booked_seats (
            seat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            show_id INTEGER NOT NULL,
            seat_number INTEGER NOT NULL CHECK(seat_number > 0),
            booking_id INTEGER NOT NULL,
            UNIQUE(show_id, seat_number),
            FOREIGN KEY(show_id) REFERENCES shows(show_id),
            FOREIGN KEY(booking_id) REFERENCES bookings(booking_id)
        );
        """)

        conn.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", password_hash("admin123"), "admin")
        )
        conn.execute(
            "INSERT OR IGNORE INTO users(username, password_hash, role) VALUES (?, ?, ?)",
            ("customer", password_hash("cust123"), "customer")
        )

        # Add sample movies and shows only when the database is empty.
        count = conn.execute("SELECT COUNT(*) FROM movies").fetchone()[0]
        if count == 0:
            cur1 = conn.execute(
                "INSERT INTO movies(title, genre, duration_minutes, language) VALUES (?, ?, ?, ?)",
                ("The Last Frame", "Thriller", 128, "Malayalam")
            )
            cur2 = conn.execute(
                "INSERT INTO movies(title, genre, duration_minutes, language) VALUES (?, ?, ?, ?)",
                ("Beyond the Sky", "Drama", 115, "English")
            )
            movie1, movie2 = cur1.lastrowid, cur2.lastrowid
            today = datetime.now().date().isoformat()
            conn.execute(
                """INSERT INTO shows(movie_id, show_date, show_time, screen_name, ticket_price, total_seats)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (movie1, today, "18:30", "Screen 1", 150.0, 40)
            )
            conn.execute(
                """INSERT INTO shows(movie_id, show_date, show_time, screen_name, ticket_price, total_seats)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (movie2, today, "21:00", "Screen 2", 180.0, 30)
            )

def read_int(prompt, minimum=1):
    while True:
        try:
            value = int(input(prompt).strip())
            if value < minimum:
                print(f"Enter a number >= {minimum}.")
                continue
            return value
        except ValueError:
            print("Please enter a valid whole number.")

def register():
    print("\n=== Customer Registration ===")
    username = input("Choose username: ").strip()
    password = getpass("Choose password: ")
    if not username or not password:
        print("Username and password are required.")
        return
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO users(username, password_hash, role) VALUES (?, ?, 'customer')",
                (username, password_hash(password))
            )
        print("Registration successful. You can now log in.")
    except sqlite3.IntegrityError:
        print("That username is already taken.")

def login():
    print("\n=== Movie Ticket Booking System ===")
    username = input("Username: ").strip()
    password = getpass("Password: ")
    with connect() as conn:
        user = conn.execute(
            "SELECT user_id, username, role FROM users WHERE username=? AND password_hash=?",
            (username, password_hash(password))
        ).fetchone()
    if user:
        print(f"Welcome, {user[1]}! Role: {user[2]}")
        return {"user_id": user[0], "username": user[1], "role": user[2]}
    print("Invalid username or password.")
    return None

def list_movies():
    with connect() as conn:
        rows = conn.execute(
            "SELECT movie_id, title, genre, duration_minutes, language FROM movies WHERE active=1 ORDER BY title"
        ).fetchall()
    if not rows:
        print("No movies currently available.")
        return
    print("\nAVAILABLE MOVIES")
    print("ID | Title | Genre | Duration | Language")
    print("-" * 70)
    for r in rows:
        print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} min | {r[4]}")

def list_shows(movie_id=None):
    sql = """
        SELECT s.show_id, m.title, s.show_date, s.show_time, s.screen_name,
               s.ticket_price, s.total_seats,
               s.total_seats - (SELECT COUNT(*) FROM booked_seats bs WHERE bs.show_id=s.show_id)
        FROM shows s JOIN movies m ON m.movie_id=s.movie_id
        WHERE m.active=1
    """
    params = []
    if movie_id is not None:
        sql += " AND s.movie_id=?"
        params.append(movie_id)
    sql += " ORDER BY s.show_date, s.show_time"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    if not rows:
        print("No shows found.")
        return []
    print("\nAVAILABLE SHOWS")
    print("Show ID | Movie | Date | Time | Screen | Price | Available Seats")
    print("-" * 90)
    for r in rows:
        print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | ₹{r[5]:.2f} | {r[7]}/{r[6]}")
    return rows

def book_ticket(user):
    list_movies()
    movie_id = read_int("\nEnter movie ID: ")
    shows = list_shows(movie_id)
    if not shows:
        return
    valid_show_ids = [row[0] for row in shows]
    show_id = read_int("Enter show ID: ")
    if show_id not in valid_show_ids:
        print("That show does not belong to the selected movie.")
        return
    seat_count = read_int("Number of tickets: ")
    try:
        with connect() as conn:
            show = conn.execute(
                "SELECT ticket_price, total_seats FROM shows WHERE show_id=?", (show_id,)
            ).fetchone()
            already_booked = conn.execute(
                "SELECT COUNT(*) FROM booked_seats WHERE show_id=?", (show_id,)
            ).fetchone()[0]
            available = show[1] - already_booked
            if seat_count > available:
                print(f"Only {available} seat(s) available.")
                return
            # Assign the first available seat numbers.
            taken = {r[0] for r in conn.execute(
                "SELECT seat_number FROM booked_seats WHERE show_id=?", (show_id,)
            ).fetchall()}
            seats = []
            for number in range(1, show[1] + 1):
                if number not in taken:
                    seats.append(number)
                if len(seats) == seat_count:
                    break
            total = show[0] * seat_count
            cur = conn.execute(
                """INSERT INTO bookings(user_id, show_id, seat_count, total_amount, status, booked_at)
                   VALUES (?, ?, ?, ?, 'BOOKED', ?)""",
                (user["user_id"], show_id, seat_count, total, datetime.now().isoformat(timespec="seconds"))
            )
            booking_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO booked_seats(show_id, seat_number, booking_id) VALUES (?, ?, ?)",
                [(show_id, seat, booking_id) for seat in seats]
            )
        print("\nBOOKING CONFIRMED")
        print(f"Booking ID : {booking_id}")
        print(f"Movie show : {show_id}")
        print(f"Seats      : {', '.join(map(str, seats))}")
        print(f"Tickets    : {seat_count}")
        print(f"Total      : ₹{total:.2f}")
        print("Keep your Booking ID for viewing or cancellation.")
    except sqlite3.IntegrityError as exc:
        print(f"Booking could not be completed: {exc}")

def my_bookings(user):
    with connect() as conn:
        rows = conn.execute("""
            SELECT b.booking_id, m.title, s.show_date, s.show_time, b.seat_count,
                   b.total_amount, b.status,
                   GROUP_CONCAT(bs.seat_number, ', ')
            FROM bookings b
            JOIN shows s ON s.show_id=b.show_id
            JOIN movies m ON m.movie_id=s.movie_id
            LEFT JOIN booked_seats bs ON bs.booking_id=b.booking_id
            WHERE b.user_id=?
            GROUP BY b.booking_id
            ORDER BY b.booking_id DESC
        """, (user["user_id"],)).fetchall()
    if not rows:
        print("You have no bookings.")
        return
    print("\nMY BOOKINGS")
    for r in rows:
        print(f"Booking #{r[0]} | {r[1]} | {r[2]} {r[3]} | Seats: {r[7] or '-'} | "
              f"Tickets: {r[4]} | ₹{r[5]:.2f} | {r[6]}")

def cancel_booking(user):
    my_bookings(user)
    booking_id = read_int("\nBooking ID to cancel: ")
    with connect() as conn:
        row = conn.execute(
            "SELECT status FROM bookings WHERE booking_id=? AND user_id=?",
            (booking_id, user["user_id"])
        ).fetchone()
        if not row:
            print("Booking not found for this account.")
            return
        if row[0] == "CANCELLED":
            print("This booking is already cancelled.")
            return
        conn.execute("UPDATE bookings SET status='CANCELLED' WHERE booking_id=?", (booking_id,))
        conn.execute("DELETE FROM booked_seats WHERE booking_id=?", (booking_id,))
    print("Booking cancelled. Seats are now available again.")

def admin_add_movie():
    title = input("Movie title: ").strip()
    genre = input("Genre: ").strip()
    duration = read_int("Duration in minutes: ")
    language = input("Language: ").strip()
    if not title or not genre or not language:
        print("All movie fields are required.")
        return
    with connect() as conn:
        conn.execute(
            "INSERT INTO movies(title, genre, duration_minutes, language) VALUES (?, ?, ?, ?)",
            (title, genre, duration, language)
        )
    print("Movie added.")

def admin_add_show():
    list_movies()
    movie_id = read_int("Movie ID for this show: ")
    with connect() as conn:
        exists = conn.execute("SELECT 1 FROM movies WHERE movie_id=? AND active=1", (movie_id,)).fetchone()
    if not exists:
        print("Invalid movie ID.")
        return
    show_date = input("Show date (YYYY-MM-DD): ").strip()
    show_time = input("Show time (HH:MM, 24-hour): ").strip()
    screen = input("Screen name: ").strip()
    price = read_int("Ticket price in rupees: ", 0)
    seats = read_int("Total seats: ")
    try:
        datetime.strptime(show_date, "%Y-%m-%d")
        datetime.strptime(show_time, "%H:%M")
    except ValueError:
        print("Date/time format is invalid.")
        return
    with connect() as conn:
        conn.execute(
            """INSERT INTO shows(movie_id, show_date, show_time, screen_name, ticket_price, total_seats)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (movie_id, show_date, show_time, screen, price, seats)
        )
    print("Show added.")

def admin_manage_movies():
    print("\n1. Add movie\n2. Deactivate movie\n3. View movies")
    choice = input("Choose: ").strip()
    if choice == "1":
        admin_add_movie()
    elif choice == "2":
        list_movies()
        movie_id = read_int("Movie ID to deactivate: ")
        with connect() as conn:
            cur = conn.execute("UPDATE movies SET active=0 WHERE movie_id=?", (movie_id,))
        print("Movie deactivated." if cur.rowcount else "Movie not found.")
    elif choice == "3":
        list_movies()
    else:
        print("Invalid option.")

def admin_report():
    with connect() as conn:
        rows = conn.execute("""
            SELECT m.title, COUNT(CASE WHEN b.status='BOOKED' THEN 1 END) AS bookings,
                   COALESCE(SUM(CASE WHEN b.status='BOOKED' THEN b.total_amount ELSE 0 END), 0) AS revenue
            FROM movies m
            LEFT JOIN shows s ON s.movie_id=m.movie_id
            LEFT JOIN bookings b ON b.show_id=s.show_id
            GROUP BY m.movie_id
            ORDER BY revenue DESC
        """).fetchall()
    print("\nADMIN BOOKING REPORT")
    for title, count, revenue in rows:
        print(f"{title}: {count} active booking(s), revenue ₹{revenue:.2f}")

def customer_menu(user):
    while True:
        print("""
--- CUSTOMER MENU ---
1. View movies
2. View all shows
3. Book tickets
4. My bookings
5. Cancel booking
0. Logout
""")
        choice = input("Choose: ").strip()
        try:
            if choice == "1": list_movies()
            elif choice == "2": list_shows()
            elif choice == "3": book_ticket(user)
            elif choice == "4": my_bookings(user)
            elif choice == "5": cancel_booking(user)
            elif choice == "0":
                print("Logged out.")
                return
            else: print("Invalid option.")
        except (sqlite3.Error, ValueError) as exc:
            print(f"Operation failed: {exc}")

def admin_menu():
    while True:
        print("""
--- ADMIN MENU ---
1. Manage movies
2. Add show
3. View shows
4. Booking and revenue report
0. Logout
""")
        choice = input("Choose: ").strip()
        try:
            if choice == "1": admin_manage_movies()
            elif choice == "2": admin_add_show()
            elif choice == "3": list_shows()
            elif choice == "4": admin_report()
            elif choice == "0":
                print("Logged out.")
                return
            else: print("Invalid option.")
        except (sqlite3.Error, ValueError) as exc:
            print(f"Operation failed: {exc}")

def main():
    setup_database()
    print(f"Database ready: {DB_NAME}")
    while True:
        print("\n1. Login\n2. Register customer\n0. Exit")
        choice = input("Choose: ").strip()
        if choice == "1":
            user = login()
            if user:
                if user["role"] == "admin":
                    admin_menu()
                else:
                    customer_menu(user)
        elif choice == "2":
            register()
        elif choice == "0":
            print("Goodbye.")
            break
        else:
            print("Invalid option.")

if __name__ == "__main__":
    main()
