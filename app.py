import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
    # api_key = "pk_4f865f73776848bcb41e369b94515e67"
    # if not os.environ.get(api_key):
    #     raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    # Ensure responses aren't cached
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Homepage after Login
@app.route("/")
@login_required
def index():
    # Show portfolio of stocks

    # Query "declaration" for better readability
    # Query for for getting symbol and shares_amount for the buy recap
    query_1 = "SELECT symbol, shares_amount FROM users_portfolio WHERE user_id = ?"
    # Query for getting user cash
    query_2 = "SELECT cash FROM users WHERE id = ?"
    # Query for getting user username
    query_3 = "SELECT username FROM users WHERE id = ?"
    # Query for deleting user's empty stocks
    query_4 = "DELETE FROM users_portfolio WHERE shares_amount = 0"
    # If some of the user's stock are empty, delete record from db with this query
    db.execute("DELETE FROM users_portfolio WHERE shares_amount = 0")

    # Get stock type and quantity
    buyRecap = db.execute(query_1, session["user_id"])

    sharesValue = 0
    for i in range(len(buyRecap)):
        # Get today shares' value
        tmp = lookup(buyRecap[i]["symbol"])
        buyRecap[i]["share_value"] = tmp["price"]
        # Calculate tot value of shares possessed
        buyRecap[i]["tot_value"] = buyRecap[i]["share_value"] * buyRecap[i]["shares_amount"]
        buyRecap[i]["tot_value"] = round(buyRecap[i]["tot_value"], 2)
        # Calculate total shares value
        sharesValue += buyRecap[i]["tot_value"]

    # User's actual cash
    actualCash = db.execute(query_2, session["user_id"])
    # Calculate possible total cash (with shares selling)
    totalCash = actualCash[0]["cash"] + sharesValue

    username = db.execute(query_3, session["user_id"])
    # Show page
    return render_template("index.html", webRecap=buyRecap, userCash=actualCash[0]["cash"],
                           userTotalCash=totalCash, webUsername=username[0]["username"])


@app.route("/add-cash", methods=["GET", "POST"])
@login_required
def addCash():
    # User add more cash to his financies

    # Query define for better readability
    # Query to get current user cash
    query_1 = "SELECT cash FROM users WHERE id = ?"
    # Query to insert new user cash
    query_2 = "UPDATE users SET cash = ? WHERE id = ?"

    # Get current user cash
    appCurrentUserCash = db.execute(query_1, session["user_id"])

    # Form sended
    if request.method == "POST":
        # Handling input errors
        # Add cash field blank
        if not request.form.get("add_cash"):
            return apology("AMOUNT TO ADD FIELD can't be BLANK")
        # Add cash not a float or a number
        try:
            float(request.form.get("add_cash"))
        except ValueError:
            return apology("AMOUNT TO ADD FIELD only accepts NUMBERS")
        # Add cash <= 0
        if float(request.form.get("add_cash")) <= 0:
            return apology("AMOUNT TO ADD can't be 0 or LESS")

        # Add current user cash to the added cash amount
        addedCash = float(request.form.get("add_cash"))
        newUserCash = float(appCurrentUserCash[0]["cash"]) + addedCash

        # Insert new user cash value in DB
        db.execute(query_2, newUserCash, session["user_id"])

        # Redirect to success page
        return redirect("/add-cash-success")

    # Landed on page, give page
    else:
        return render_template("add-cash.html", webCurrentUserCash=appCurrentUserCash[0]["cash"])


# Added cash successfully
@app.route("/add-cash-success")
@login_required
def addCashSuccess():
    return render_template("add-cash-success.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    # Buy shares of stock

    # Query "declaration" for better readability
    # Query for getting cash
    query_1 = "SELECT cash FROM users WHERE users.id = ?"
    # Query for updating cash
    query_2 = "UPDATE users SET cash = ? WHERE users.id = ?"
    # Query for inserting new record in transaction_history
    query_3 = "INSERT INTO transaction_history (user_id, symbol, shares_amount, share_value, transaction_date, transaction_type) VALUES (?, ?, ?, ?, ?, 'BUY')"
    # Query for checking if a stock has already been bought
    query_4 = "SELECT symbol FROM users_portfolio WHERE user_id = ? AND symbol = ?"
    # Query for taking user shares
    query_5 = "SELECT shares_amount FROM users_portfolio WHERE user_id = ? AND symbol = ?"
    # Query for updating user_portfolio if a stock has already been bought
    query_6 = "UPDATE users_portfolio SET shares_amount = ? WHERE user_id = ? AND symbol = ?"
    # Query for inserting a new bought stock in user_portfolio
    query_7 = "INSERT INTO users_portfolio (user_id, symbol, shares_amount) VALUES (?, ?, ?)"

    # Form submit
    # Check fields
    if request.method == "POST":
        # Check if is float hard-coded (the input field already handle floats)
        for i in request.form.get("shares"):
            if not i.isdigit():
                return apology("CAN'T BUY FRACTIONAL AMOUNT OF SHARES")

        # Symbol field empty, throw error
        if not request.form.get("symbol").upper():
            return apology("SYMBOL FIELD can't be BLANK")
        # Symbol not found
        elif lookup(request.form.get("symbol").upper()) == None:
            return apology("SYMBOL NOT FOUND")

        # Shares field empty, throw error
        elif not request.form.get("shares"):
            return apology("SHARES FIELD can't be BLANK")
        # Invalid shares number (can't buy negative amount of stocks)
        elif int(request.form.get("shares")) <= 0:
            return apology("SHARES NUMBER can't be NULL or NEGATIVE")

        # Check if cash is enough
        tmpCash = db.execute(query_1, session["user_id"])
        currentCash = tmpCash[0]["cash"]

        # Stock Price
        tmpStockPrice = lookup(request.form.get("symbol").upper())
        stockPrice = tmpStockPrice["price"]
        # Error: too much shares to buy
        if currentCash < (stockPrice * int(request.form.get("shares"))):
            return apology("CAN'T AFFORD this much SHARES")

        # Setting new cash
        currentCash -= stockPrice * int(request.form.get("shares"))
        db.execute(query_2, currentCash, session["user_id"])

        # Update transaction_history
        db.execute(query_3, session["user_id"], request.form.get("symbol").upper(),
                   request.form.get("shares"), stockPrice, datetime.now().strftime("%Y-%m-%d, %H:%M:%S"))

        # If stock already bought, update shares_amount
        if len(db.execute(query_4, session["user_id"], request.form.get("symbol").upper())) > 0:
            userShares = db.execute(query_5, session["user_id"], request.form.get("symbol"))
            totalUserShares = int(request.form.get("shares")) + int(userShares[0]["shares_amount"])
            db.execute(query_6, totalUserShares, session["user_id"], request.form.get("symbol").upper())
        # Otherwise, insert the stock
        else:
            db.execute(query_7, session["user_id"], request.form.get("symbol").upper(), request.form.get("shares"))

        # Redirect to index page
        return redirect("/")
    # Landed on the page, get the page
    else:
        return render_template("buy.html", cash=db.execute(query_1, session["user_id"]))


@app.route("/edit-password", methods=["GET", "POST"])
@login_required
def editPassword():
    # Change user password

    # Query declaration for better readability
    # Query for checking user password
    query_1 = "SELECT hash FROM users WHERE id = ?"
    # Query for updating user password
    query_2 = "UPDATE users SET hash = ? WHERE id = ?"

    # Form sent. Change the password
    if request.method == "POST":
        # Handle errors: password field
        # Old password field blank
        if not request.form.get("old_psw"):
            return apology("OLD PASSWORD field can't be BLANK")
        # Old password != user password
        oldPSW = db.execute(query_1, session["user_id"])
        if not check_password_hash(oldPSW[0]["hash"], request.form.get("old_psw")):
            return apology("OLD PASSWORD don't match with YOUR PASSWORD")

        # New password field blank
        if not request.form.get("new_psw"):
            return apology("NEW PASSWORD field can't be BLANK")
        # New password = user password
        if check_password_hash(oldPSW[0]["hash"], request.form.get("new_psw")):
            return apology("NEW PASSWORD must be different from OLD PASSWORD")
        # New password requisites not satisfied:
        errCode = PasswordRequisites(request.form.get("new_psw"))
        if errCode == "ERR1":
            return apology("PASSWORD LENGHT must be at least 12 CHARACTERS LONG")
        elif errCode == "ERR2":
            return apology("PASSWORD must contain AT LEAST 1 UPPER AND LOWER CASE LETTER")
        elif errCode == "ERR3":
            return apology("PASSWORD must contain AT LEAST 1 NUMBER")
        elif errCode == "ERR4":
            return apology("PASSWORD must cointain AT LEAST 1 SPECIAL CHARACTER")

        # Confirm password field blank
        if not request.form.get("new_confirm"):
            return apology("CONFIRM PASSWORD field can't be BLANK")
        # Confirm password != new password
        if request.form.get("new_psw") != request.form.get("new_confirm"):
            return apology("NEW PASSWORD don't match with CONFIRMATION ONE")

        # Update user password with new hashed one
        hashPSW = generate_password_hash(request.form.get("new_psw"), method='pbkdf2:sha256', salt_length=8)
        db.execute(query_2, hashPSW, session["user_id"])

        # Show success page
        return redirect("/edit-psw-success")
    # Landed on page, get the page
    else:
        return render_template("edit-password.html")


@app.route("/edit-psw-success")
def editSuccess():
    # Shows edit success page

    # Make the user login again
    session.clear()

    return render_template("edit-psw-success.html")


@app.route("/history")
@login_required
def history():
    # Show history of user's transactions

    # Query "declaration" for better readability
    # Query for history transaction
    query_1 = "SELECT symbol, shares_amount, share_value, transaction_date, transaction_type FROM transaction_history WHERE user_id = ?"

    # History transaction view
    appHistory = db.execute(query_1, session["user_id"])
    # Get the page
    return render_template("history.html", webHistory=appHistory)


@app.route("/login", methods=["GET", "POST"])
def login():
    # Log user in

    # Query "declaration" for better readability
    # Query for checking if username already exists
    query_1 = "SELECT * FROM users WHERE username = ?"

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("MUST provide USERNAME", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("MUST provide PASSWORD", 403)

        # Query database for username
        rows = db.execute(query_1, request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("INVALID USERNAME or PASSWORD", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    # Log user out

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


# Get info about stocks quotes
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    # Get stock quote.

    # Form submitted
    if request.method == "POST":
        # If symbol not exists, throw error page
        if lookup(request.form.get("symbol").upper()) == None:
            return apology("Symbol not Found")
        # Otherwise get infos
        return render_template("quoted.html", searchedSymbol=lookup(request.form.get("symbol").upper()))
    # Page visited, get page
    else:
        return render_template("quote.html")


# Registration function
@app.route("/register", methods=["GET", "POST"])
def register():
    # Register user

    # Query "declaration" for better readability
    # Query to get username
    query_1 = "SELECT username FROM users WHERE username = ?"
    # Query to insert data in users
    query_2 = "INSERT INTO users (username, hash) VALUES (?, ?)"

    # Form compiled and submitted
    if request.method == "POST":
        # Handling Username Input fails
        # Username blank
        if not request.form.get("username"):
            return apology("USERNAME FIELD can't be left BLANK")
        # Username exists
        elif db.execute(query_1, request.form.get("username")):
            return apology("USERNAME already exists")

        # Handling Password Fails
        # Password blank
        if not request.form.get("password"):
            return apology("PASSWORD FIELD can't be left BLANK")

        # Check password requisites
        errCode = PasswordRequisites(request.form.get("password"))
        if errCode == "ERR1":
            return apology("PASSWORD LENGHT must be at least 12 CHARACTERS LONG")
        elif errCode == "ERR2":
            return apology("PASSWORD must contain AT LEAST 1 UPPER AND LOWER CASE LETTER")
        elif errCode == "ERR3":
            return apology("PASSWORD must contain AT LEAST 1 NUMBER")
        elif errCode == "ERR4":
            return apology("PASSWORD must cointain AT LEAST 1 SPECIAL CHARACTER")

        # Password and Confirmation not equals
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("PASSWORD and CONFIRMATION PASSWORD FIELDS must MATCH")

        # Check passed, inserting data in DB
        hashPSW = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)
        db.execute(query_2, request.form.get("username"), hashPSW)
        return redirect("/registration-success")
    # Reaches the page
    else:
        return render_template("register.html")


# Sell function
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    # Sell shares of stock

    # Query string separated for read facility
    # Query for checking stock possession
    query_1 = "SELECT * FROM users_portfolio WHERE user_id = ? AND symbol = ?"
    # Query for checking if possessed shares_amount is enough and for selling selection
    query_2 = "SELECT shares_amount FROM users_portfolio WHERE user_id = ? AND symbol = ?"
    # Query for updating share_amount after selling
    query_3 = "UPDATE users_portfolio SET shares_amount = ? WHERE user_id = ? AND symbol = ?"
    # Query for getting user's cash value
    query_4 = "SELECT cash FROM users WHERE id = ?"
    # Query for updating user cash after selling
    query_5 = "UPDATE users SET cash = ? WHERE id = ?"
    # Query for inserting selling transaction in transaction_history
    query_6 = "INSERT INTO transaction_history (user_id, symbol, shares_amount, share_value, transaction_date, transaction_type) VALUES (?, ?, ?, ?, ?, 'SELL')"
    # Query for stocks' symbols owned by user
    query_7 = "SELECT symbol FROM users_portfolio WHERE user_id = ?"

    # Form submission
    if request.method == "POST":
        # Handling bad inputs
        # No input in symbol field
        if request.form.get("symbol") == None:
            return apology("SYMBOL FIELD can't be BLANK")
        if not request.form.get("symbol").upper():
            return apology("SYMBOL FIELD can't be BLANK")
        # Input symbol not found
        elif lookup(request.form.get("symbol").upper()) == None:
            return apology("SYMBOL not FOUND")
        # Input symbol not possessed
        elif len(db.execute(query_1, session["user_id"], request.form.get("symbol").upper())) == 0:
            return apology("YOU DON'T POSSESS THE INSERTED SYMBOL")

        # No input in shares field
        if not request.form.get("shares"):
            return apology("SHARES FILED can't be BLANK")
        # Shares negative or 0
        if int(request.form.get("shares")) <= 0:
            return apology("CAN'T SELL 0 or LESS SHARES")
        # Shares too high for possessed ones
        if int(request.form.get("shares")) > int((db.execute(query_2,
                                                             session["user_id"], request.form.get("symbol").upper()))[0]["shares_amount"]):
            return apology("CAN'T SELL MORE SHARES THAN POSSESSED ONES")

        # Sell process
        # Calculating new user's shares amount
        userShares = db.execute(query_2, session["user_id"], request.form.get("symbol").upper())
        updatedUserShares = int(userShares[0]["shares_amount"]) - int(request.form.get("shares"))
        # Update DB
        db.execute(query_3, updatedUserShares, session["user_id"], request.form.get("symbol").upper())

        # Calculating sell amount
        sharesTodayValue = lookup(request.form.get("symbol").upper())
        sellAmount = sharesTodayValue["price"] * int(request.form.get("shares"))

        # Get cash
        userCash = db.execute(query_4, session["user_id"])
        updatedUserCash = userCash[0]["cash"] + sellAmount
        # Update DB
        db.execute(query_5, updatedUserCash, session["user_id"])

        # Register transaction into DB
        db.execute(query_6, session["user_id"], request.form.get("symbol").upper(),
                   request.form.get("shares"), sharesTodayValue["price"], datetime.now().strftime("%Y-%m-%d, %H:%M:%S"))

        # Redirect to index page
        return redirect("/")

    # Landed on the page, render template
    else:
        # Query symbols to give to the web-page for the select menu
        appSymbols = db.execute(query_7, session["user_id"])
        return render_template("sell.html", webSymbols=appSymbols)


# Registration Success
@app.route("/registration-success")
def success():
    return render_template("registration-success.html")


# Function for checking if string has any number
def ContainsNumber(inputString):
    # Check if "number" variable is a number for every character in the given string
    return any(number.isdigit() for number in inputString)


# Function for checking if string has special characters
def ContainsSpecial(inputString):
    return any(not char.isalnum() for char in inputString)


# Function for checking if password requisites are satisfied
def PasswordRequisites(inputPSW):
    # Lenght >= 12
    if not len(inputPSW) >= 12:
        return "ERR1"
    # Both upper and lower case characters
    elif not (not inputPSW.isupper() and not inputPSW.islower()):
        return "ERR2"
    # At least one number
    elif not ContainsNumber(inputPSW):
        return "ERR3"
    # Special Character
    elif not ContainsSpecial(inputPSW):
        return "ERR4"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))