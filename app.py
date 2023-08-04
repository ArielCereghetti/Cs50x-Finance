import os
import datetime as time
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
import random
from helpers import apology, login_required, lookup, usd


# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config['UPLOAD_FOLDER'] = './static'

Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    try:

        # Store the user's name for later usage
        user = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])[0][
            "username"
        ]
    except:
        session.clear()
        return redirect("/login")
    # Store the user's current cash.
    user_cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
    user_cash = round(user_cash[0]["cash"], 2)

    # Store the shares that the user has, grouping them by it's symbol
    shares = db.execute(
        "SELECT symbol, amount FROM stocks_owned WHERE username = ?", user
    )

    # If the user has no shares, render the default template.
    if not shares:
        return render_template("index.html", name=user,cash=format(round(float(user_cash), 2), ','))

    # Prepare to store all the user's stocks
    stocks = []
    # for every share in shares's table
    for s in shares:
        # Search for the current price of the share
        look = (lookup(s["symbol"]))["price"]

        # Store the share with it's updated data and the price of the whole shares together.
        s = {
            "symbol": s["symbol"],
            "price": look,
            "amount": s["amount"],
            "full": round(look * s["amount"], 2),
        }

        # Finally store this instance of "s" into stocks's array.
        stocks.append(s)

    # Store the sum of all stocks's prices + the cash the user currently has.
    user_wealth = db.execute(
        "SELECT symbol, amount FROM stocks_owned WHERE username = ?", user
    )
    wealth = user_cash
    # For every row in the "user_wealth" table, multiply the current price of the stocks he has + the amount of cash he has
    for row in user_wealth:
        price = lookup(row["symbol"])["price"]
        wealth += price * row["amount"]

    return render_template(
        "index.html", name=user, stocks=stocks, cash=format(user_cash, ','), sum=format(round(wealth, 2), ',')
    )


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        if request.form.get("name"):
            name = request.form.get("name")
            if name not in db.execute("SELECT username FROM users WHERE username = ?",
                       name):
                db.execute("UPDATE TABLE users SET username = ? WHERE id = ?", name, session['user_id'])
            else:
                return apology("That username already exists")



    try:
        return render_template("profile.html", image=session['user_img'])
    except KeyError:
        session['user_img'] = 'noprof.png'
        return render_template("profile.html", image="noprof.png")


@app.route("/upload.html", methods=["GET"])
@login_required
def return_pic():
    return render_template("upload.html")


@app.route("/upload_img", methods=["POST"])
@login_required
def upload_pic():
    if 'profile_pic' in request.files:
        pic = request.files['profile_pic']

        for ext in [".png", ".jpeg", ".jpg"]:
            if pic.filename.endswith(ext):
                extension = ext


        if  extension:
            saved = False
            for i in range(0, 300):
                pic.filename = i
                picname = str(pic.filename) + extension
                if not os.path.isfile("./static/" + picname):
                    pic.save("./static/" + picname)
                    saved = True
                    if session['user_img'] != 'noprof.png':
                        os.remove("./static/" + session['user_img'])
                    break


            if not saved:
                return apology("No space in memory", 400)



            session['user_img'] = picname
            db.execute("UPDATE users SET img = ? WHERE id = ?", picname, session['user_id'])
            return redirect("/profile")
        else:
            return apology("Not a valid filetype", 403)

    return apology("No picture uploaded", 403)






@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")

        # if there are no shares
        if not request.form.get("shares"):
            return apology("Not a valid number of shares")

        # if the user didn't imput a symbol, return
        if not symbol:
            return apology("To buy a symbol... insert a symbol")

        try:
            amount = int(request.form.get("shares"))
        except:
            return apology("Not a valid number of shares", 400)

        # If the user inputted a number less than one or no number, return
        if not amount > 0:
            return apology("Not a valid number of shares", 400)

        look = lookup(symbol)

        # if there was no stock found, return
        if not look:
            return apology("Invalid symbol")

        # Store the user's name based on the session id.
        user = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
        user = user[0]["username"]

        # Select the current amount of cash of the user
        cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])
        cash = cash[0]["cash"]

        # Calculate the cost of the shares bought
        cash_after = cash - (look["price"] * round(float(amount), 2))

        # If it's too expensive, return and do not make the transaction
        if not cash_after > 0:
            return apology("You cannot afford this transaction")

        # if everything went well, make the transaction, storing the username, symbol, price, amount of stocks,
        # and the current date. Then redirect the user to the main page.
        db.execute(
            "INSERT INTO movements(username, symbol, price, amount, day, month, hour, minute) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            user,
            symbol,
            look["price"],
            amount,
            time.date.today().day,
            time.date.today().month,
            time.datetime.now().hour,
            time.datetime.now().minute,
        )
        has = db.execute(
            "SELECT * FROM stocks_owned WHERE username = ? AND symbol = ?", user, symbol
        )
        if has:
            db.execute(
                "UPDATE stocks_owned SET amount = amount + ? WHERE username = ? AND symbol = ?",
                amount,
                user,
                symbol,
            )
        else:
            db.execute(
                "INSERT INTO stocks_owned(symbol, amount, username) VALUES(?, ?, ?)",
                symbol,
                amount,
                user,
            )

        db.execute("UPDATE users SET cash = ? WHERE username = ?", cash_after, user)

        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])[0][
        "username"
    ]

    data = db.execute("SELECT * FROM movements WHERE username = ?", user)

    if data:
        return render_template("history.html", data=data)
    else:
        return render_template("history.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["username"] = rows[0]["username"]
        session["user_img"] = rows[0]["img"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        look = lookup(request.form.get("symbol"))
        if not look:
            return apology("Not a valid symbol")
        print(look)
        return render_template("quoted.html", name=look['symbol'], price=str(look['price']), symbol=look['symbol'])

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("Must provide a username")
        if not request.form.get("password") or len(request.form.get("password")) < 8:
            return apology("Must provide a valid password (8 characters)")
        if not request.form.get("confirmation"):
            return apology("Must repeat the password to verify it's correct")
        if request.form.get("confirmation") != request.form.get("password"):
            return apology("passwords must be equal")


        usr = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )
        for data in usr:
            if request.form.get("username") == data["username"]:
                return apology("username already exists")

        db.execute(
            "INSERT INTO users(username, hash, img) VALUES(?, ?, ?)",
            request.form.get("username"),
            generate_password_hash(
                request.form.get("password"), method="pbkdf2:sha256"
            ), "noprof.png"
        )


        return redirect("/login")
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        #   initialize some useful variables
        user = db.execute("SELECT username FROM users WHERE id = ?", session["user_id"])
        user = user[0]["username"]
        symbol = request.form.get("symbol")

        #   if there is no symbol or the symbol is invalid
        if not symbol:
            return apology("Invalid symbol", 403)
        look = lookup(symbol)
        if not look:
            return apology("Invalid symbol", 403)

        #   Check and store if the user has shares of that type
        user_shares = db.execute(
            "SELECT id, symbol, amount FROM stocks_owned WHERE symbol = ? AND username = ?",
            symbol,
            user,
        )
        if not user_shares:
            return apology("You don't have that stock in your account", 403)

        user_shares = user_shares[0]

        #   if the user forgot to insert the amount of shares
        amount = request.form.get("shares")
        if not amount:
            return apology("Not a valid amount of shares")

        #   set shares from str to int
        amount = int(amount)
        if amount < 1:
            return apology("Not a valid amount of shares")

        if symbol not in user_shares.values():
            # this explains what it does
            return apology("You don't have that share available in your account")

        if amount > user_shares["amount"]:
            # this explains what it does
            return apology("You don't have enough shares to sell")

        price = round(float(look["price"]), 2)

        #   if the user wants to sell all his shares, Delete it from the database

        if amount == user_shares["amount"]:
            db.execute(
                "DELETE FROM stocks_owned WHERE symbol = ? AND username = ?",
                symbol,
                user,
            )

        #   if the user wants to sell some stocks, sell the right amount.
        elif amount < user_shares["amount"]:
            db.execute(
                "UPDATE stocks_owned SET amount = amount - ? WHERE symbol = ?",
                amount,
                symbol,
            )
        else:
            return apology("something went wrong :(")

        db.execute(
            "UPDATE users SET cash = cash + ? WHERE username = ?",
            round(price * amount, 2),
            user,
        )

        db.execute(
            "INSERT INTO movements(username, symbol, price, amount, day, month, hour, minute, method) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            user,
            symbol,
            look["price"],
            amount,
            time.date.today().day,
            time.date.today().month,
            time.datetime.now().hour,
            time.datetime.now().minute,
            "sell",
        )

        return redirect("/")

    return render_template("sell.html")
