#!/usr/bin/env bash

build.sh
#Sair imediatamente se um comando falhar
set -o errexit

#Instalar as dependências do Python
pip install -r requirements.txt

#Aplicar as migrações do banco de dados (cria as tabelas)
flask db upgrade

echo "Build finalizado com sucesso!"
