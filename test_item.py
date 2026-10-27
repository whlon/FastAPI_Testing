#Prior to running this application, 
# run the following in the terminal
# python3 -m venv venv 
# source venn/Bin/activate 
# pip install pytest httpx
# pytest test_item.py 

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from main import app 
from models.database import Base,get_db
from models.itemModel import Item

# ---------------------------------------------------------------------------
# Test setup: controlled test data
# ---------------------------------------------------------------------------
 
# Separate in-memory SQLite database used only for testing, so the real
# database is never touched. StaticPool makes every connection share the
# same in-memory database.

# Controlled test data: a separate in-memory database, wiped after every test
test_engine = create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool)

TestingSessionLocal = sessionmaker(autocommit=False,autoflush = False,bind = test_engine)

# Replacement for the app's get_db dependency: hands each request a session
# connected to the test database instead of the real one.
def override_get_db():
    db=TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Fixture run before every test: creates empty tables, swaps in the test
# database, and provides a TestClient built from the app object.
# Afterwards it removes the override and drops the tables, so every test
# starts with a clean, empty database.     
@pytest.fixture
def client():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    try: 
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

# TC01 - Successful write (POST)
# Requirement: a user can create a product.
# Sends a valid item and checks the API returns 201 Created, gives the first
# item id 1, and returns the same name, price and stock status that was sent.
def test_create_item(client):
    item_data ={
        "name":"Laptop",
        "price":50000,
        "in_stock":True
    }
    response =client.post("/item",json=item_data)
    assert response.status_code ==201
    data = response.json()
    assert data["id"]==1
    assert data["name"] =="Laptop"
    assert data["price"]==50000
    assert data["in_stock"] is True

# TC02 - Invalid request body (error scenario)
# Requirement: invalid product data is rejected.
# Sends an item with the required "price" field missing and checks the API
# refuses it with 422 Unprocessable Entity, as defined by the API contract.
def test_create_item_invalid_data(client):
    item_data ={"name":"Laptop","in_stock":True}
    response = client.post("/item",json = item_data)
    assert response.status_code ==422


# TC03 - Successful retrieval of all items (GET)
# Requirement: a user can view all products.
# Creates one item, then checks GET /items returns 200 and a list containing
# exactly that one item, proving nothing extra or missing is returned.
def test_Get_all_itmes(client):
    client.post("/item",json={
        "name":"Laptop",
        "price":50000,
        "in_stock":True
    })
    response = client.get("/items")
    assert response.status_code ==200
    assert len(response.json()) ==1
    assert response.json()[0]["name"]=="Laptop"

 #TC04 - Successful retrieval of a single item (GET)
# Requirement: a user can view a single product by its id.
# Creates an item, reads its id from the response, then checks GET /item/{id}
# returns 200 with the matching id and name.
def test_get_single_item(client):
    create_response = client.post("/item",json={
        "name":"Mouse",
        "price":500,
        "in_stock":True
    })
    item_id = create_response.json()["id"]
    response = client.get(f"/item/{item_id}")
    assert response.status_code==200
    assert response.json()["id"] == item_id
    assert response.json()["name"] =="Mouse"

# TC05 - Unknown resource identifier (error scenario)
# Requirement: requesting a product that does not exist returns an error.
# The database is empty, so id 854 cannot exist. Checks the API returns
# 404 Not Found with the expected error message.
def test_get_item_not_fount(client):
    response = client.get("/item/854")
    assert response.status_code ==404
    assert response.json()["detail"] == "Item not found "

# TC06 - Successful update (PUT)
# Requirement: a user can update an existing product.
# Creates an item, sends new values with PUT, and checks the API returns 200
# with the updated name, price and stock status.
def test_update_item(client):
    create_response = client.post("/item",json={"name":"Mouse","price":500,"in_stock":True})
    item_id = create_response.json()["id"]
    
    updated_data = {"name":"Mouse updated","price":511,"in_stock":False}
    response = client.put(f"/item/{item_id}",json= updated_data)
    assert response.status_code ==200
    assert response.json()["name"] =="Mouse updated"
    assert response.json()["price"] ==511
    assert response.json()["in_stock"] ==False

# TC07 - Successful delete (DELETE)
# Requirement: a user can delete a product.
# Creates an item, deletes it, and checks the API returns 200 with a success
# message and the deleted id. Then tries to GET the same item to confirm it
# has really been removed (expects 404).
def test_delete_item(client):
    create_response = client.post("/item",json={"name":"Mouse","price":500,"in_stock":True})
    item_id = create_response.json()["id"]
    response = client.delete(f"/item/{item_id}")
    assert response.status_code ==200
    assert response.json()["message"] =="Item deleted Successfully"
    assert response.json()["id"] == item_id
    
    get_response = client.get(f"/item/{item_id}")
    assert get_response.status_code == 404
    