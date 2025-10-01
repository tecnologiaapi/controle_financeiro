#!/usr/bin/env bash
# build.sh

# Sair imediatamente se um comando falhar
set -o errexit

# Instalar as dependências do Python
pip install -r requirements.txt

# Criar as tabelas do banco de dados
# (Isso executará o comando db.create_all() no contexto da sua aplicação)
flask shell <<< "from app import db; db.create_all()"

echo "Build finalizado com sucesso!"