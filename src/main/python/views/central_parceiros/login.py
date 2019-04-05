from webapp import application, db
from models.table_parceiros import Parceiros
from flask import request, jsonify, make_response, redirect, url_for, session
from flask_cors import cross_origin
from werkzeug.security import check_password_hash
from werkzeug.wrappers import Response
from werkzeug.datastructures import Headers
import jwt
import datetime
from functools import wraps
from flasgger.utils import swag_from
from flask_dance.contrib.facebook import make_facebook_blueprint, facebook
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.consumer.backend.sqla import SQLAlchemyBackend
from flask_dance.consumer import oauth_authorized
from models.table_oauth import OAuth
from sqlalchemy.orm.exc import NoResultFound

import os 
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

google_blueprint = make_google_blueprint(
    client_id="1092697945658-mm49tuj821b1a3jni5epplc0l54ofj0s.apps.googleusercontent.com",
    client_secret="XSK0EQfS9PEG3KN9bUySkjsz",
    scope=[
        "https://www.googleapis.com/auth/plus.me",
        "https://www.googleapis.com/auth/userinfo.email",
    ]
)
blFacebook = make_facebook_blueprint(
    client_id="381484502603093",
    client_secret="1558acef090349bdedfc13c075d573cb",
    scope=[
        "email",
    ])

application.register_blueprint(google_blueprint, url_prefix='/google_login')
application.register_blueprint(blFacebook, url_prefix="/login")

google_blueprint.backend = SQLAlchemyBackend(OAuth, db.session, user_required=False)
blFacebook.backend = SQLAlchemyBackend(OAuth, db.session, user_required=False)


def token_required(f):
    @wraps(f)
    def decoreted(*args, **kwargs):
        token = None

        if 'token' in request.headers:
            token = request.headers['token']

        # if session['token']:
        #     token = session['token']
        
        if not token:
            return jsonify({'Mensagem': 'Você precisa de uma Token para ter acesso!'}), 401
        try:
            data = jwt.decode(token, application.config['SECRET_KEY'])
            current_user = Parceiros.query.filter_by(id_geral = data['id_geral']).first()
        except:
            return jsonify({'Mensagem': 'Token invalida!'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decoreted


@application.route('/login', methods=['POST'])
@swag_from('../swagger_specs/autenticacao/login.yml', methods=['POST'])
def login():
    auth = request.get_json()
    if not auth or not auth['username'] or not auth['password']:
        return make_response('Não foi possivel verificar', 401, {'WWW-Authenticate': 'Basic realm="Login required!"'})
    
    parceiro = Parceiros.query.filter_by(email = auth['username']).first()

    if not parceiro:
        return jsonify({'Mensagem': 'Não foi possivel verificar'})
    
    if check_password_hash(parceiro.senha, auth['password']):
        token = jwt.encode({'id_geral': parceiro.id_geral, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes = 40)}, application.config['SECRET_KEY'])
        
        # session['token'] = token.decode('UTF-8')
        # return jsonify({'Mensagem': 'Bem Vindo {}!'.format(parceiro.nome)})
        return jsonify({'token': token.decode('UTF-8')})
    
    return jsonify({'Mensagem': 'Senha Incorreta!'})

@application.route('/login/google', methods=['GET', 'POST'])
@cross_origin()
def google_login():
    resp = redirect(url_for('google.login'))

    # resp.headers['Access-Control-Allow-Origin'] = 'http://localhost:4200'
    # resp.headers = Headers({'Access-Control-Allow-Origin': 'http://localhost:4200'})
    # resp.headers = Headers.add_header('Access-Control-Allow-Origin', 'http://localhost:4200')
    resp.headers = {
        'Access-Control-Allow-Origin': '*', 
        'Location': 'http://localhost:8080/google_login/google'
    }
    # resp.headers.set('Access-Control-Allow-Origin', 'http://localhost:4200')
    # resp.headers.add('Access-Control-Allow-Origin', 'http://localhost:4200')

    return resp

@oauth_authorized.connect_via(google_blueprint)
def google_logged_in(blueprint, token):
    account_info = blueprint.session.get('/oauth2/v2/userinfo')

    if account_info.ok:
        account_info_json = account_info.json()

        parceiro = Parceiros.query.filter_by(email=account_info_json['email']).first()

        if not parceiro:
            parceiro = Parceiros(
                nivel='Parceiro', 
                email=account_info_json['email'], 
                senha='Google account', 
                validado=False
            )
            db.session.add(parceiro)
            db.session.commit()

        
        token = jwt.encode({'id_geral': parceiro.id_geral, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes = 40)}, application.config['SECRET_KEY'])
        # response = make_response()
        # response.headers.set('Access-Control-Allow-Origin', '*')

        return jsonify({'token': token.decode('UTF-8')})


@application.route("/facebook")
@cross_origin(origin='*')
def facebook_login():
    resp = redirect(url_for('facebook.login'))
    return resp

@oauth_authorized.connect_via(blFacebook)
def facebook_logged_in(blFacebook, token):

    account_info = blFacebook.session.get("/me?&fields={fields}".format(fields=['email, first_name, last_name']))

    if account_info.ok:
        account_info_json = account_info.json()
        print(account_info_json)

        query = Parceiros.query.filter_by(email = account_info_json['email'])

        try:
            parceiro = query.one()
        except NoResultFound:
            parceiro = Parceiros(
                nivel='Parceiro',
                email= account_info_json['email'], 
                senha='Facebook account', 
                validado= True
            )

            parceiro.nome = account_info_json['first_name']
            parceiro.sobrenome = account_info_json['last_name'] 

            db.session.add(parceiro)
            db.session.commit()

        token = jwt.encode({'id_geral': parceiro.id_geral, 'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes = 40)}, application.config['SECRET_KEY'])
        return jsonify({'token': token.decode('UTF-8')})     