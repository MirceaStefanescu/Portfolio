def test_create_and_get_product(client):

    payload = {
        "name": "Coffee Beans",
        "description": "1kg bag",
        "price_cents": 1899,
        "currency": "usd",
    }

    response = client.post("/products", json=payload)
    assert response.status_code == 201
    product = response.json()
    assert product["currency"] == "USD"

    get_response = client.get(f"/products/{product['id']}")
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["name"] == payload["name"]


def test_empty_name_update_is_rejected_and_delete_has_no_body(client):
    created = client.post(
        "/products", json={"name": "Coffee", "price_cents": 500, "currency": "USD"}
    ).json()
    path = f"/products/{created['id']}"
    assert client.put(path, json={"name": ""}).status_code == 422
    assert client.get(path).json()["name"] == "Coffee"
    deleted = client.delete(path)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get(path).status_code == 404
