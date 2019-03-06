from flask import Flask, render_template, request, redirect,jsonify, url_for, flash
from flask import session as login_session
from flask import make_response

from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker, scoped_session
from database_setup import Base, Restaurant, MenuItem, User
import random, string

from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

import json
import httplib2
import requests
import pprint
app = Flask(__name__)

CLIENT_SECRETS_DATA = open('client_secrets.json', 'r').read()
print()
print('DADOS LIDOS DO CLIENT_SECRETS:')
print(CLIENT_SECRETS_DATA)
print()
CLIENT_ID = json.loads(CLIENT_SECRETS_DATA)['web']['client_id']
print('ID DO CLIENT - NOSSA APLICACAO:')
print(CLIENT_ID)
print()
#Connect to Database and create database session
engine = create_engine('sqlite:///restaurantmenuwithusers.db', connect_args = {'check_same_thread':False})
Base.metadata.bind = engine

session = scoped_session(sessionmaker(bind=engine))

def createNewUser(login_session):
  newUser = User(name = login_session['username'], email = login_session['email'], picture = login_session['picture'])
  session.add(newUser)
  session.commit()
  user = session.query(User).filter_by(email = login_session['email']).one()
  return user.id

def getUserInfos(user_id):
  try:
    user = session.query(User).filter_by(id = user_id).one()
    return user
  except:
    return None

def getUserId(user_email):
  try:
    user_id = session.query(User).filter_by(email = user_email).one()
    return user_id
  except:
    return None

@app.route('/login')
def showLogin():
  state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(32))
  login_session['state'] = state
  return render_template('login.html', STATE=state)

@app.route('/gconnect', methods=['POST'])
def gconnect():
  print()
  print('TOKEN DE SESSÃO DO NOSSO APP')
  print(login_session['state'])
  request.args.get('state')
  if request.args.get('state') != login_session['state']:
    response = make_response(json.dumps('Parece que você ainda não se autenticou na nossa aplicação...'), 401)
    response.headers['Content-Type'] = 'application/json'
    return response
  code = request.data

  try:
    oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
    oauth_flow.redirect_uri = 'postmessage'
    credentials = oauth_flow.step2_exchange(code)
    print()
    print('TODOS OS ATRIBUTOS DO OBJETO DE CREDENCIAL')
    pprint.pprint(credentials.__dict__)
  except FlowExchangeError as error:
    print(error)
    response = make_response(json.dumps('Não foi possivel criar um objeto de credencial.'), 401)
    response.headers['Content-type'] = 'application/json'
    return response
  
  print()
  print('FAZENDO REQUISIÇÃO PARA VALIDAR O TOKEN CARREGADO')
  access_token = credentials.access_token
  url = 'https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' % access_token
  httplib = httplib2.Http()
  resultado_request = httplib.request(url, 'GET')
  print(resultado_request[0])
  print(resultado_request[1])
  print()
  print('PASSANDO O RESULTADO DA REQUESTS DE JSON PARA DICIONARIO')
  resultado_request_json = json.loads(resultado_request[1])
  print(resultado_request_json)
  if resultado_request_json.get('error') is not None:
    response = make_response(json.dumps(resultado_request_json.get('error')), 401)
    response.headers['Content-Type'] = 'application/json'
    return response

  gplus_id = credentials.id_token['sub']
  print(gplus_id)
  if resultado_request_json['user_id'] != gplus_id:
    response = make_response(json.dumps('O token não pertence ao usuario atual.'), 401)
    response.headers['Content-Type'] = 'application/json'
    return response
  
  if resultado_request_json['issued_to'] != CLIENT_ID:
    response = make_response (json.dumps('O token usado é direcionado a outro app.'), 401)
    response.headers['Content-Type'] = 'application/json'
    return response

  token_armazenado = login_session.get('access_token')
  id_gplus_usuario = login_session.get('gplus_id')
  if token_armazenado is not None and gplus_id == id_gplus_usuario:
    response = make_response(json.dumps('Usuario ja efetuou login anteriormente.'), 200)
    response.headers['Content-Type'] = 'application/json'
    return response
  login_session['access_token'] = credentials.access_token
  login_session['gplus_id'] = gplus_id

  url = 'https://www.googleapis.com/oauth2/v1/userinfo'
  params = {'access_token': credentials.access_token, 'alt': 'json'}
  resposta = requests.get(url,params=params)
  print()
  print('BUSCANDO INFORMAÇÕES DO USUARIO')
  print(resposta)
  pprint.pprint(resposta.json())
  dados_resposta = resposta.json()
  login_session['username'] = dados_resposta['name']
  login_session['email'] = dados_resposta['email']
  login_session['picture'] = dados_resposta['picture']
  print()
  print('CHECANDO SE O USUARIO JA EXISTE NOS REGISTROS DO NOSSO SISTEMA')
  user_id = getUserId(login_session['email'])
  print()
  print('ID RELACIONADO AO EMAIL: %s' % login_session['email'])
  print(user_id)
  if not user_id:
    user_id = createNewUser(login_session)
    print()
    print('O ID RELACIONADO AO EMAIL: %s' % login_session['email'])
    print(user_id)
  login_session['user_id'] = user_id
  output = ''
  output += '<img src="' + login_session['picture'] + '" style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;">'
  output += '<h1>' + login_session['username'] + '</h1>'
  output += '<span>' + login_session['email'] + '</span>'
  
  return output

@app.route('/gdisconnect')
def gdisconnect():
  token_acesso = login_session['access_token']
  if token_acesso is None:
    response = make_response(json.dumps('Não há usuarios logados para desconectar.'), 401)
    response.headers['Content-Type'] = 'application/json'
    return response
  
  url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' %login_session['access_token']
  httplib = httplib2.Http()
  resposta = httplib.request(url, 'GET')[0]

  print()
  print('RESPOSTA DA TENTATIVA DE DESLOGAR DA CONTA')
  print(resposta)
  if resposta['status'] == '200':
    del login_session['access_token']
    del login_session['gplus_id']
    del login_session['username']
    del login_session['email']
    del login_session['picture']
    response = make_response(json.dumps('Desconectado com sucesso, redirecionando...'), 200)
    response.headers['Content-Type'] = 'application/json'
    return response
  else:
    response = make_response(json.dumps('Falha ao tentar desconectar da conta.'), 400)
    response.headers['Content-Type'] = 'application/json'
    return response
#JSON APIs to view Restaurant Information
@app.route('/restaurant/<int:restaurant_id>/menu/JSON')
def restaurantMenuJSON(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    items = session.query(MenuItem).filter_by(restaurant_id = restaurant_id).all()
    return jsonify(MenuItems=[i.serialize for i in items])


@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/JSON')
def menuItemJSON(restaurant_id, menu_id):
    Menu_Item = session.query(MenuItem).filter_by(id = menu_id).one()
    return jsonify(Menu_Item = Menu_Item.serialize)

@app.route('/restaurant/JSON')
def restaurantsJSON():
    restaurants = session.query(Restaurant).all()
    return jsonify(restaurants= [r.serialize for r in restaurants])


#Show all restaurants
@app.route('/')
@app.route('/restaurant/')
def showRestaurants():
  restaurants = session.query(Restaurant).order_by(asc(Restaurant.name))
  for i in restaurants:
    print(i.__dict__)
  if 'username' not in login_session:
    return render_template('publicrestaurants.html', restaurants=restaurants)
  return render_template('restaurants.html', restaurants = restaurants)

#Create a new restaurant
@app.route('/restaurant/new/', methods=['GET','POST'])
def newRestaurant():
  if 'username' not in login_session:
    return redirect('/login')
  if request.method == 'POST':
      newRestaurant = Restaurant(name = request.form['name'], user_id = login_session['user_id'])
      session.add(newRestaurant)
      flash('New Restaurant %s Successfully Created' % newRestaurant.name)
      session.commit()
      return redirect(url_for('showRestaurants'))
  else:
      return render_template('newRestaurant.html')

#Edit a restaurant
@app.route('/restaurant/<int:restaurant_id>/edit/', methods = ['GET', 'POST'])
def editRestaurant(restaurant_id):
  editedRestaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
  print('DADOS')
  print(editRestaurant.__dict__)
  if 'username' not in login_session or editedRestaurant.user_id != login_session['user_id']:
    return redirect('/login')
  if request.method == 'POST':
      if request.form['name']:
        editedRestaurant.name = request.form['name']
        flash('Restaurant Successfully Edited %s' % editedRestaurant.name)
        return redirect(url_for('showRestaurants'))
  else:
    return render_template('editRestaurant.html', restaurant = editedRestaurant)


#Delete a restaurant
@app.route('/restaurant/<int:restaurant_id>/delete/', methods = ['GET','POST'])
def deleteRestaurant(restaurant_id):
  restaurantToDelete = session.query(Restaurant).filter_by(id = restaurant_id).one()
  if 'username' not in login_session or restaurantToDelete.user_id != login_session['user_id']:
    return redirect('/login')
  
  if request.method == 'POST':
    session.delete(restaurantToDelete)
    flash('%s Successfully Deleted' % restaurantToDelete.name)
    session.commit()
    return redirect(url_for('showRestaurants', restaurant_id = restaurant_id))
  else:
    return render_template('deleteRestaurant.html',restaurant = restaurantToDelete)

#Show a restaurant menu
@app.route('/restaurant/<int:restaurant_id>/')
@app.route('/restaurant/<int:restaurant_id>/menu/')
def showMenu(restaurant_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).first()
    items = session.query(MenuItem).filter_by(restaurant_id = restaurant_id).all()
    creator = getUserInfos(restaurant.user_id)
    print(restaurant.user_id)
    if 'user_id' not in login_session or restaurant.user_id != login_session['user_id']:
        return render_template('publicmenu.html', items=items, restaurant=restaurant, creator=creator)
    print(login_session['user_id'])
    return render_template('menu.html', items = items, restaurant = restaurant, creator=creator)

#Create a new menu item
@app.route('/restaurant/<int:restaurant_id>/menu/new/',methods=['GET','POST'])
def newMenuItem(restaurant_id):
  if 'username' not in login_session:
    return redirect('/login')
  restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
  if request.method == 'POST':
      newItem = MenuItem(name = request.form['name'], description = request.form['description'], price = request.form['price'], course = request.form['course'], restaurant_id = restaurant_id)
      session.add(newItem)
      session.commit()
      flash('New Menu %s Item Successfully Created' % (newItem.name))
      return redirect(url_for('showMenu', restaurant_id = restaurant_id))
  else:
      return render_template('newmenuitem.html', restaurant_id = restaurant_id)

#Edit a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/edit', methods=['GET','POST'])
def editMenuItem(restaurant_id, menu_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if 'username' not in login_session or restaurant.user_id != login_session['user_id']:
      return redirect('/login')
    editedItem = session.query(MenuItem).filter_by(id = menu_id).one()
    
    if request.method == 'POST':
        if request.form['name']:
            editedItem.name = request.form['name']
        if request.form['description']:
            editedItem.description = request.form['description']
        if request.form['price']:
            editedItem.price = request.form['price']
        if request.form['course']:
            editedItem.course = request.form['course']
        session.add(editedItem)
        session.commit() 
        flash('Menu Item Successfully Edited')
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))
    else:
        return render_template('editmenuitem.html', restaurant_id = restaurant_id, menu_id = menu_id, item = editedItem)


#Delete a menu item
@app.route('/restaurant/<int:restaurant_id>/menu/<int:menu_id>/delete', methods = ['GET','POST'])
def deleteMenuItem(restaurant_id,menu_id):
    restaurant = session.query(Restaurant).filter_by(id = restaurant_id).one()
    if 'username' not in login_session or restaurant.user_id != login_session['user_id']:
      return redirect('/login')
    
    itemToDelete = session.query(MenuItem).filter_by(id = menu_id).one() 
    if request.method == 'POST':
        session.delete(itemToDelete)
        session.commit()
        flash('Menu Item Successfully Deleted')
        return redirect(url_for('showMenu', restaurant_id = restaurant_id))
    else:
        return render_template('deleteMenuItem.html', item = itemToDelete)




if __name__ == '__main__':
  app.secret_key = 'super_secret_key'
  app.debug = True
  app.run(host = '0.0.0.0', port = 5000)
