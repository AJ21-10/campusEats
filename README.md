# CampusEats
Team 15 :
Team Lead : Anurag Panda
Members :   i) Taj Ansari
            ii) Dinesh Kushwaha
            iii)Rohit
            iv) Pushpender

CampusEats is a campus-focused food discovery and ordering platform designed specifically for students, food vendors, delivery staff, and campus administrators.

The project is being developed as part of **CS 543 — Web Services** and will gradually evolve from a basic web application into a service-oriented system.

## Project Vision

CampusEats aims to make campus food services easier to discover, order, manage, and track.

Students can discover restaurants, browse menus, check food availability, add items to their cart, place immediate or scheduled orders, choose pickup or delivery, participate in group orders, track their orders, and submit ratings and reviews.

Food vendors can manage their restaurants, menus, prices, availability, operating hours, and incoming orders.

The system is designed specifically for campus environments rather than as a general-purpose food delivery platform.

## Key Features

### Student Features

* User registration and login
* Profile and campus location management
* Restaurant discovery
* Menu browsing
* Food availability checking
* Cart management
* Immediate ordering
* Scheduled ordering
* Group ordering
* Pickup and campus delivery
* Order tracking
* Notifications
* Ratings and reviews
* Order history

### Vendor Features

* Restaurant management
* Menu management
* Price management
* Food availability management
* Operating hours
* Order management
* Preparation status updates

### Delivery Features

* Delivery assignment
* Delivery status updates
* Campus delivery tracking
* Pickup and delivery confirmation

### Administration Features

* User management
* Vendor management
* Restaurant approval
* Campus location management
* Order monitoring
* System reports

## What Makes This Project Different?

The project takes the basic CampusEats concept discussed in the course material and extends it for a more realistic campus environment.

The major additions planned for this implementation are:

* Scheduled food orders
* Group orders
* Campus-specific pickup points
* Food-item availability management
* Restaurant and food-item ratings
* Campus-specific delivery
* Vendor operating hours

These features will allow the project to be developed beyond the basic restaurant → cart → order → payment → delivery flow.

## Planned Architecture

The project will initially be developed incrementally as a web application.

As the system grows, its capabilities can be separated into independent services based on data ownership.

Possible future services include:

```text
Accounts
Catalogue
Orders
Payments
Delivery
Notifications
Reviews
```

Each service will own its relevant data and expose operations through a defined API contract.

For example:

```text
Orders
   |
   | checkItem(itemId)
   v
Catalogue

Orders
   |
   | charge(amount, method)
   v
Payments

Orders
   |
   | assignDelivery(orderId)
   v
Delivery
```

The services will communicate through their contracts instead of directly accessing each other's internal database structures.

This follows the service-boundary approach covered in the CS 543 course material, where capabilities are identified first, grouped by data ownership, separated into boundaries, and then given explicit contracts.

## Repository Structure

```text
campuseats/
│
├── README.md
│
└── docs/
    ├── http-log.md
    ├── network-analysis.md
    └── brief.md
```

## Documentation

| File                       | Description                                                                 |
| -------------------------- | --------------------------------------------------------------------------- |
| `README.md`                | Project overview, goals, features, and planned architecture                 |
| `docs/http-log.md`         | HTTP request and response experiments using curl                            |
| `docs/network-analysis.md` | Browser Network panel and waterfall analysis                                |
| `docs/brief.md`            | CampusEats system brief, users, nouns, verbs, and future service boundaries |

## Development Roadmap

### Phase 1 — Web and HTTP Fundamentals

* HTTP requests and responses
* HTTP methods
* Status codes
* Headers
* JSON
* REST-style APIs
* Browser Network analysis

### Phase 2 — Core CampusEats

* User accounts
* Restaurants
* Menus
* Cart
* Orders
* Payment workflow
* Pickup and delivery

### Phase 3 — Campus-Specific Features

* Scheduled orders
* Group orders
* Pickup points
* Restaurant operating hours
* Item availability
* Ratings and reviews

### Phase 4 — Web Services

* Define service boundaries
* Define API contracts
* Separate data ownership
* Implement inter-service communication
* Handle service errors
* Maintain loose coupling

### Phase 5 — Deployment and Improvement

* Testing
* Authentication and authorization
* Logging
* Error handling
* API documentation
* Deployment
* Performance improvements

## Course

**CS 543 — Web Services**

**Project:** CampusEats

## Status

Currently in the initial HTTP and project setup stage.

The project will be developed incrementally throughout the course.
