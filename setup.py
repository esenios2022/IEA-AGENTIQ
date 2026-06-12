from setuptools import find_packages, setup

setup(
    name="iea-agentiq",
    version="0.1.0",
    description="Plataforma de IA para agentes autónomos",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.29.0",
        "sqlalchemy>=2.0.0",
        "psycopg2-binary>=2.9.0",
        "alembic>=1.13.0",
        "redis>=5.0.0",
        "pydantic>=2.6.0",
        "pydantic-settings>=2.2.0",
        "python-dotenv>=1.0.0",
    ],
)
