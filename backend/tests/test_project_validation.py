def test_patch_rejects_null_project_name(client):
    created = client.post("/api/v1/projects", json={"name": "Valid name"})
    project_id = created.json()["id"]
    response = client.patch(f"/api/v1/projects/{project_id}", json={"name": None})
    assert response.status_code == 422
