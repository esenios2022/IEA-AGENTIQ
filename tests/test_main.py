from fastapi.testclient import TestClient

from src.config import settings
from src.main import app

ADMIN_AUTH = (settings.admin_user, settings.admin_password)

with TestClient(app) as client:

    def test_health_check():
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_home_page():
        response = client.get("/")
        assert response.status_code == 200
        assert "IEA AGENTIQ" in response.text

    def test_home_has_stats_band():
        response = client.get("/")
        assert "stats-band" in response.text
        assert 'id="resultados"' in response.text

    def test_home_has_especializacion_and_lema():
        response = client.get("/")
        assert 'id="especializacion"' in response.text
        assert "agentificado" in response.text.lower()
        assert "desde cero" in response.text.lower()

    def test_home_has_mision():
        response = client.get("/")
        assert 'id="mision"' in response.text
        assert "tiempo de vida" in response.text.lower()
        assert "visión clara" in response.text.lower()

    def test_create_lead():
        response = client.post(
            "/api/leads",
            json={"nombre": "Juan", "email": "juan@test.com", "empresa": "ACME"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["nombre"] == "Juan"
        assert data["email"] == "juan@test.com"

    def test_create_lead_invalid_email():
        response = client.post(
            "/api/leads",
            json={"nombre": "Ana", "email": "no-es-email"},
        )
        assert response.status_code == 422

    def test_admin_leads_requires_auth():
        response = client.get("/admin/leads")
        assert response.status_code == 401

    def test_admin_leads_with_auth():
        response = client.get("/admin/leads", auth=ADMIN_AUTH)
        assert response.status_code == 200
        assert "Leads recibidos" in response.text

    def test_admin_leads_search():
        client.post(
            "/api/leads",
            json={"nombre": "Buscable", "email": "buscable@test.com", "empresa": "FindMe"},
        )
        response = client.get("/admin/leads", params={"q": "FindMe"}, auth=ADMIN_AUTH)
        assert response.status_code == 200
        assert "buscable@test.com" in response.text

    def test_admin_leads_pagination():
        for i in range(25):
            client.post(
                "/api/leads",
                json={"nombre": f"Pag{i}", "email": f"pag{i}@test.com"},
            )
        response = client.get(
            "/admin/leads", params={"page": 1, "per_page": 10}, auth=ADMIN_AUTH
        )
        assert response.status_code == 200
        assert "Página 1 de" in response.text

    def test_admin_leads_chart():
        client.post(
            "/api/leads",
            json={"nombre": "Chart", "email": "chart@test.com"},
        )
        response = client.get("/admin/leads", auth=ADMIN_AUTH)
        assert response.status_code == 200
        assert "Leads por día" in response.text

    def test_export_leads_requires_auth():
        response = client.get("/admin/leads/export")
        assert response.status_code == 401

    def test_export_leads_csv():
        client.post(
            "/api/leads",
            json={"nombre": "Export", "email": "export@test.com", "empresa": "CSV Co"},
        )
        response = client.get("/admin/leads/export", auth=ADMIN_AUTH)
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        body = response.text
        assert "id,nombre,email,empresa,created_at" in body
        assert "export@test.com" in body
