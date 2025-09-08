# Parkinson Artifical Intelligence Diagnosis System

## Project info
We are SmartSystem Lab aim to create a application to aid doctors in assessing patients condition with parkinson disease over time.

## Setup
The instructions are for if you use Visual Studio Code. They can be used as a guide for a IDE of your preference.

We use Docker to automatically create the environment to run the code. We use a Docker Compose file because we run multiple services at the same time.

You will be required to have:
- Docker
- Dev Containers Extension

Below will be the steps on how to setup and run the application in a IDE.

'''sh
# Step 1: Clone the repository
git clone <url_link>

# Step 2: Open Project
code <path>

# Step 3: Run the Docker Compose file
docker compose up
'''
Now you can just click on the localhost link and you can use the program

**Editing Code**
The system we have in place to edit the code uses Dev Containers to reduce development issues like dependencies missing. This also solves the issue of your IDE missing modules as well.

You can only work on one container at a time. To modify if you want to work on the frontend or back end head to .devcontainers/devcontainers.json

Afterwards, run the command Reopen in Container.

**Frontend template made with Loveable AI**
Template is modifed to fit our needs.

**URL**: https://lovable.dev/projects/85901f50-9fff-403c-8869-9128963fa80e

## What technologies are used for this project?

This project is built with:

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS
