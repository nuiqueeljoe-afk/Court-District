# Court District

**Business idea:** Court District is a basketball shoe shop for players who need court-ready footwear. This system presents the shop and its shoe lineup, lets customers save pairs to a personal list, and gives staff a place to manage inventory.

> Before building or submitting, check with your class that this business and inventory workflow have not already been claimed.

## Problem

Small basketball shoe shops need a simple way to show available shoes and keep product details and stock up to date. Court District brings the public catalog and staff inventory management together in one small web app.

## Features

- Public, responsive storefront with shop information, services, and shoe catalog.
- Registration, login, and logout. Passwords are hashed with Werkzeug.
- Regular customers can manage their own wishlist and shopping cart, including size and quantity.
- Checkout supports store pickup or cash on delivery, records orders, and updates stock. Payment is simulated; no card details are collected.
- Customers can review their order history and order details.
- Admins can create, view, edit, and delete shoe records. Deletion requires browser confirmation.
- Required-field, number, email, and password validation with readable messages.
- SQLite storage persists users, inventory, and favorites across restarts.
- CSRF tokens on form submissions and server-side role and ownership checks.

## Tech Stack

- Python 3.10+
- Flask
- SQLite
- HTML, CSS, and Jinja templates

## Setup and Run

1. Install Python 3.10 or newer.
2. From the project folder, create and activate a virtual environment:

	```sh
	python3 -m venv .venv
	source .venv/bin/activate
	```

3. Install dependencies:

	```sh
	pip install -r requirements.txt
	```

4. Start with sample shoes and local-only demo accounts:

	```sh
	DEMO_MODE=1 python app.py
	```

	Visit <http://127.0.0.1:5000>.

	Demo admin: `manager@courtdistrict.test` / `DistrictDemo1!`

	Demo customer: `player@courtdistrict.test` / `CourtSide1!`

	Demo accounts are for local evaluation only. Do not enable `DEMO_MODE` on a public deployment. For a non-demo run, set a private `SECRET_KEY` before starting the app. To provision an admin account, set `ADMIN_EMAIL` and `ADMIN_PASSWORD` before first startup; the app creates that account as an admin. Otherwise, new registrations are regular customers.

The database is created as `court_district.db` in the project folder. Set `DATABASE_PATH` to use a different location. Keep the database and credentials out of source control.

## Roles

- **Admin:** manage the shoe catalog and stock.
- **Customer:** browse the public catalog and manage their own saved shoes.

## AI Tools

GitHub Copilot was used to help scaffold the application, styling, and documentation. The project owner should review and be ready to explain the code before submitting.

## Originality and Submission

Confirm the idea is available with classmates before claiming it. Submit the GitHub repository link as instructed by the teacher. This repository contains the source; the app does not need any API keys.