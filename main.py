from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_bootstrap import Bootstrap
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_wtf import FlaskForm, RecaptchaField
from wtforms import StringField, SubmitField, FloatField, PasswordField, IntegerField
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from wtforms.validators import DataRequired, Length
import random
import os

app = Flask(__name__)
Bootstrap(app)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
db = SQLAlchemy(app)

RECAPTCHA_PUBLIC_KEY = "6LeYIbsSAAAAACRPIllxA7wvXjIE411PfdB2gt2J"
RECAPTCHA_PRIVATE_KEY = "6LeYIbsSAAAAAJezaIq3Ft_hSTo0YtyeFG-JgRtu"

app.config.from_object(__name__)

# FLASK LOGIN
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))


class Users(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    tokens = db.Column(db.Integer)

    buyer_items = relationship("Items", back_populates='user')
    creator_item = relationship("CreatorItem", back_populates="creator")


class Items(db.Model, UserMixin):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), nullable=False)
    little_description = db.Column(db.String(250), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(250), nullable=False)
    final_price = db.Column(db.Integer, nullable=False)

    winner = db.Column(db.Integer, db.ForeignKey("users.id"))
    user = relationship("Users", back_populates='buyer_items')

    item = relationship("CreatorItem", back_populates="item")


class CreatorItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    creator_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    creator = relationship("Users", back_populates="creator_item")

    item_id = db.Column(db.Integer, db.ForeignKey("items.id"))
    item = relationship("Items", back_populates="item")


class SignUpForm(FlaskForm):
    email = StringField("Podaj swoj email:", validators=[DataRequired()])
    login = StringField("Podaj swoj login:", validators=[DataRequired()])
    password = PasswordField("Podaj haslo: ", validators=[DataRequired()])
    recaptcha = RecaptchaField()
    sign_up = SubmitField("Sign up")


class LogInForm(FlaskForm):
    login = StringField("Podaj swoj login:", validators=[DataRequired()])
    password = PasswordField("Podaj haslo: ", validators=[DataRequired()])
    log_in = SubmitField("Log In")


class CreateAuction(FlaskForm):
    title = StringField("Podaj tytul", validators=[DataRequired()])
    little_description = StringField("Krotki opis", validators=[DataRequired(), Length(min=0, max=50)])
    price = FloatField("Podaj cene produktu", validators=[DataRequired()])
    description = StringField("Podaj opis produktu", validators=[DataRequired()])
    final_price = FloatField("Podaj cene koncowa", validators=[DataRequired()])
    submit_field = SubmitField("Create offert")


@app.route("/")
def home():
    db.create_all()
    posts = Items.query.all()
    return render_template('index.html', posts=posts, user=current_user, logged_in=current_user.is_authenticated)


@app.route("/add-item", methods=["GET", "POST"])
def add_item():
    if not current_user.is_authenticated:
        abort(403)
    form = CreateAuction()
    if form.validate_on_submit():
        new_item = Items(
            title=form.title.data,
            little_description=form.little_description.data,
            price=form.price.data,
            description=form.description.data,
            final_price=form.final_price.data,
        )
        new_creator = CreatorItem(
            creator=current_user,
            item=new_item
        )
        db.session.add(new_item)
        db.session.add(new_creator)
        db.session.commit()
        return redirect(url_for('home', user=current_user, logged_in=current_user.is_authenticated))
    return render_template('creating-auction.html', form=form, user=current_user, logged_in=current_user.is_authenticated)


@app.route("/przedmiot/<int:item_id>")
def item(item_id):
    item = Items.query.get(item_id)
    creator = CreatorItem.query.filter_by(item_id=item_id).first()
    if current_user.is_authenticated:
        if item.final_price >= item.price:
            if item.user == None:
                item.user = current_user
                db.session.commit()
    return render_template('strona-przedmiotu.html', item=item, user=current_user,
                           logged_in=current_user.is_authenticated, creator=creator)


@app.route('/sign-up', methods=["POST", "GET"])
def sign_up():
    form = SignUpForm()
    if form.validate_on_submit():
        if form.login.data == Users.query.filter_by(login=form.login.data).first():
            flash("That login already exist")
            return redirect(url_for('sign_up'))
        if form.email.data == Users.query.filter_by(email=form.email.data).first():
            flash("That email already exist")
            return redirect(url_for('sign_up'))
        new_user = Users(
            login=form.login.data,
            password=generate_password_hash(form.password.data, 'md5', 8),
            email=form.email.data,
            tokens=0
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('home'))
    return render_template('sign_up.html', form=form)


@app.route('/log-in', methods=["POST", "GET"])
def log_in():
    form = LogInForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(login=form.login.data).first()
        if not user:
            flash("User doesn't exist")
            return redirect(url_for('log_in'))
        if not check_password_hash(user.password, form.password.data):
            flash("Incorrect password")
            return redirect(url_for('log_in'))
        login_user(user)
        return redirect(url_for('home'))
    return render_template('log_in.html', form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))


@app.route("/buy-tokens")
def buy_tokens():
    if not current_user.is_authenticated:
        abort(403)
    return render_template('buy-tokens.html', user=current_user, logged_in=current_user.is_authenticated)


@app.route("/tokens/<int:tokens>")
def add_tokens(tokens):
    current_user.tokens = current_user.tokens + tokens
    db.session.commit()
    return redirect(url_for('home'))


@app.route("/less/<int:item_id>")
def less_button(item_id):
    if not current_user.is_authenticated:
        abort(403)
    if current_user.tokens < 0:
        flash("You dont have any tokens")
        return redirect(url_for('item', item_id=item_id))

    cur_item = Items.query.get(item_id)
    cur_item.price = round(cur_item.price - (random.randint(50, 150) / 100), 2)
    current_user.tokens = current_user.tokens - 1
    db.session.commit()
    return redirect(url_for('item', item_id=item_id))


if __name__ == '__main__':
    app.run(debug=True)
