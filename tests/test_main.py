import pytest


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_require_api_key(client):
    assert client.get("/health").status_code == 200


def test_identities_missing_api_key_returns_403(client):
    response = client.get("/identities/a@1")
    assert response.status_code == 403


def test_identities_wrong_api_key_returns_403(client):
    response = client.get("/identities/a@1", headers={"X-API-Key": "wrong"})
    assert response.status_code == 403


def test_identities_returns_full_group_when_found(client, auth_headers, mock_db):
    conn, cursor = mock_db
    cursor.fetchone.return_value = ("a@1", "b@2", "ddd@3")

    response = client.get("/identities/a@1", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {
        "input": "a@1",
        "linked_identities": ["a@1", "b@2", "ddd@3"],
    }
    cursor.execute.assert_called_once_with(
        "SELECT system_1_email, system_2_email, system_3_email "
        "FROM identity_links WHERE system_1_email = %s",
        ("a@1",),
    )
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "email,expected_column",
    [
        ("a@1", "system_1_email"),
        ("a@2", "system_2_email"),
        ("a@3", "system_3_email"),
    ],
)
def test_identities_uses_column_matching_email_domain(
    client, auth_headers, mock_db, email, expected_column
):
    _, cursor = mock_db
    cursor.fetchone.return_value = ("a@1", "a@2", "a@3")

    client.get(f"/identities/{email}", headers=auth_headers)

    cursor.execute.assert_called_once_with(
        f"SELECT system_1_email, system_2_email, system_3_email "
        f"FROM identity_links WHERE {expected_column} = %s",
        (email,),
    )


def test_identities_skips_null_columns(client, auth_headers, mock_db):
    _, cursor = mock_db
    cursor.fetchone.return_value = ("a@1", None, "c@3")

    response = client.get("/identities/a@1", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["linked_identities"] == ["a@1", "c@3"]


def test_identities_returns_self_when_not_found(client, auth_headers, mock_db):
    conn, cursor = mock_db
    cursor.fetchone.return_value = None

    response = client.get("/identities/x@1", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"input": "x@1", "linked_identities": ["x@1"]}
    conn.close.assert_called_once()


def test_identities_closes_connection_on_db_error(client, auth_headers, mock_db):
    conn, cursor = mock_db
    cursor.execute.side_effect = RuntimeError("db blew up")

    response = client.get("/identities/a@1", headers=auth_headers)

    assert response.status_code == 500
    conn.close.assert_called_once()


@pytest.mark.parametrize(
    "bad_email",
    [
        "a@4",          # domain digit out of range
        "a@12",         # multi-char domain
        "a@1.com",      # extra chars after digit
        "a@b",          # non-digit domain
    ],
)
def test_identities_invalid_email_returns_422(client, auth_headers, bad_email):
    response = client.get(f"/identities/{bad_email}", headers=auth_headers)
    assert response.status_code == 422
