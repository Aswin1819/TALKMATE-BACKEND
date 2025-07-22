# 🗣️ TalkMate Backend

TalkMate Backend powers a futuristic **language exchange platform** with scalable APIs, real-time WebSockets, and secure subscription management. Built with **Django REST Framework**, it manages users, rooms, subscriptions, and real-time audio/video features.

---

## **🚀 Elevator Pitch**
TalkMate is a **social language-learning platform** where people connect via **live audio/video rooms** to practice speaking. It offers:
- Real-time **group audio/video calls** (up to 6 users)
- **Premium features** like private rooms, subscriptions, and video calls
- **Admin dashboard** for user, content, and report management

---

## **🛠 Features**
- **Real-time Communication:** WebSockets via Django Channels + Redis.
- **Group Calls:** WebRTC mesh-based calls (future upgrade to MediaSoup).
- **Subscriptions:** Razorpay integration for payments & plan upgrades.
- **Admin Dashboard:** KPIs, room moderation, reports, taxonomy, subscription management.
- **Authentication:** JWT-based authentication & Google OAuth.
- **Scalable Backend:** PostgreSQL + Dockerized environment.

---

## **🛠️ Technologies Used**
- **Framework:** Django 5 + Django REST Framework
- **Real-time:** Django Channels, WebSockets, Redis
- **Auth:** JWT + Google OAuth
- **Database:** PostgreSQL
- **Media:** Cloudinary (storage)
- **Payments:** Razorpay
- **DevOps:** Docker + Docker Compose
- **Future:** Celery for background tasks (coming soon)

---

## **📁 Project Structure**
TALKMATE-BACKEND/
├── adminapp/
├── backend/
├── rooms/
├── users/
├── manage.py
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md


---

## **⚡ Quick Start**
### **1. Clone the repository**
```bash


🤝 Contributing
Contributions welcome! Open issues or PRs to improve features and fix bugs.

📬 Contact
For queries: aswinachumathra@gmail.com
