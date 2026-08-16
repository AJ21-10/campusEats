1. Aim of the Project

The aim of Campus Eats is to build a digital food ordering and delivery platform that connects students, faculty, and staff with on-campus or nearby food outlets (canteens, cafeterias, food courts, local vendors), enabling users to browse menus, place orders, make payments, and get food delivered or ready for pickup — reducing wait times and improving convenience within a campus ecosystem.

2. Requirements of the Project

Functional Requirements

User registration/login (students, vendors, delivery staff, admin)
Browse restaurants/canteens and their menus
Search and filter by cuisine, price, ratings
Add to cart, place orders, choose delivery/pickup
Online payment integration (or wallet/cash on delivery)
Order tracking (real-time status updates)
Rating and review system
Admin dashboard to manage vendors, orders, and users
Notifications (order confirmation, delivery updates)

Non-Functional Requirements

Scalability (handle peak hours like lunch breaks)
Security (data protection, secure payments)
Usability (simple, intuitive UI for students)
Performance (fast load and order processing time)
Availability (minimal downtime during campus hours)

3. Main Audience of the Project
Students – primary users ordering food between classes
Faculty/Staff – secondary users ordering during work hours
Campus food vendors/canteens – sellers managing menus and orders
Delivery personnel – campus staff or student part-timers fulfilling orders
Admin/College authority – overseeing platform operations

4. What the System Does

The system acts as a middle layer connecting customers, vendors, and delivery agents:

Customers place orders through the app/website
Orders are routed to the respective vendor for preparation
Once ready, a delivery agent (or the customer themselves) picks up and delivers/collects the order
The system tracks order status end-to-end (placed → accepted → preparing → out for delivery/ready → delivered)
Admin panel manages vendors, monitors transactions, and resolves issues

5. Technologies

i. Services (core system components/modules)

User Service – authentication, profile management
Vendor/Restaurant Service – menu management, order acceptance
Order Service – cart, checkout, order life-cycle management
Payment Service – payment gateway integration (UPI, cards, wallet)
Delivery/Tracking Service – real-time order/delivery status
Notification Service – SMS/email/push notifications
Admin Service – analytics, vendor approval, dispute handling

ii. Actions / Tasks / Contracts (typical operations within the system)

registerUser() / loginUser()
addMenuItem() / updateMenu() (vendor side)
placeOrder() / cancelOrder()
makePayment() / refundPayment()
updateOrderStatus() (accepted, preparing, delivered)
assignDelivery() / trackDelivery()
submitReview() / rateOrder()
generateReport() (admin analytics)

iii. Technology that I will use throughout the project:

Frontend: React.js 
Backend: Node.js (Express) 
Database: MongoDB 
Payment Gateway:  Stripe 
Real-time Updates: Firebase
Hosting: Vercel
