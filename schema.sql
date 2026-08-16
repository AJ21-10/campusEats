-- CampusEats — Assignment 2
-- schema.sql
--
-- Design rule:
-- Each service owns its own tables.
-- Foreign keys are used only inside a service boundary.
-- Cross-service identifiers are stored as ordinary IDs and are resolved
-- through service contracts rather than database-level foreign keys.
--
-- PostgreSQL

BEGIN;

CREATE SCHEMA IF NOT EXISTS accounts;
CREATE SCHEMA IF NOT EXISTS catalogue;
CREATE SCHEMA IF NOT EXISTS orders;
CREATE SCHEMA IF NOT EXISTS payments;
CREATE SCHEMA IF NOT EXISTS delivery;
CREATE SCHEMA IF NOT EXISTS campus_engagement;

-- ============================================================
-- 1. ACCOUNTS SERVICE
-- Owns users, profiles, campuses and user campus locations.
-- ============================================================

CREATE TABLE accounts.users (
    user_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    role            VARCHAR(30) NOT NULL
                    CHECK (role IN ('STUDENT', 'VENDOR', 'DELIVERY_STAFF', 'ADMIN')),
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'SUSPENDED', 'DISABLED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE accounts.profiles (
    user_id         BIGINT PRIMARY KEY
                    REFERENCES accounts.users(user_id) ON DELETE CASCADE,
    full_name       VARCHAR(150) NOT NULL,
    phone           VARCHAR(30),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE accounts.campuses (
    campus_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    code            VARCHAR(50) NOT NULL UNIQUE,
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE TABLE accounts.campus_locations (
    location_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT NOT NULL
                    REFERENCES accounts.users(user_id) ON DELETE CASCADE,
    campus_id       BIGINT NOT NULL
                    REFERENCES accounts.campuses(campus_id),
    label            VARCHAR(100) NOT NULL,
    building         VARCHAR(150) NOT NULL,
    room             VARCHAR(100),
    is_default       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE accounts.pickup_points (
    pickup_point_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campus_id       BIGINT NOT NULL
                    REFERENCES accounts.campuses(campus_id),
    name            VARCHAR(150) NOT NULL,
    building        VARCHAR(150) NOT NULL,
    description     TEXT,
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'INACTIVE'))
);

CREATE INDEX idx_campus_locations_user
    ON accounts.campus_locations(user_id);

CREATE INDEX idx_campus_locations_campus
    ON accounts.campus_locations(campus_id);

CREATE INDEX idx_pickup_points_campus
    ON accounts.pickup_points(campus_id);


-- ============================================================
-- 2. CATALOGUE SERVICE
-- Owns restaurants, menus, categories, menu items and hours.
--
-- owner_user_id is an Accounts service identifier.
-- It is intentionally NOT a database foreign key.
-- ============================================================

CREATE TABLE catalogue.restaurants (
    restaurant_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_user_id  BIGINT NOT NULL,
    campus_id      BIGINT NOT NULL,
    name            VARCHAR(150) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'INACTIVE', 'SUSPENDED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE catalogue.categories (
    category_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE catalogue.menus (
    menu_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    restaurant_id   BIGINT NOT NULL
                    REFERENCES catalogue.restaurants(restaurant_id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (restaurant_id, name)
);

CREATE TABLE catalogue.menu_items (
    item_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    menu_id         BIGINT NOT NULL
                    REFERENCES catalogue.menus(menu_id) ON DELETE CASCADE,
    category_id     BIGINT
                    REFERENCES catalogue.categories(category_id) ON DELETE SET NULL,
    name            VARCHAR(150) NOT NULL,
    description     TEXT,
    price           NUMERIC(10,2) NOT NULL
                    CHECK (price >= 0),
    is_available    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE catalogue.restaurant_hours (
    restaurant_id   BIGINT NOT NULL
                    REFERENCES catalogue.restaurants(restaurant_id) ON DELETE CASCADE,
    day_of_week     SMALLINT NOT NULL
                    CHECK (day_of_week BETWEEN 0 AND 6),
    opens_at        TIME,
    closes_at       TIME,
    is_closed       BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (restaurant_id, day_of_week),
    CHECK (
        (is_closed = TRUE AND opens_at IS NULL AND closes_at IS NULL)
        OR
        (is_closed = FALSE AND opens_at IS NOT NULL AND closes_at IS NOT NULL)
    )
);

CREATE INDEX idx_restaurants_owner
    ON catalogue.restaurants(owner_user_id);

CREATE INDEX idx_restaurants_campus
    ON catalogue.restaurants(campus_id);

CREATE INDEX idx_menus_restaurant
    ON catalogue.menus(restaurant_id);

CREATE INDEX idx_menu_items_menu
    ON catalogue.menu_items(menu_id);

CREATE INDEX idx_menu_items_category
    ON catalogue.menu_items(category_id);

CREATE INDEX idx_menu_items_available
    ON catalogue.menu_items(is_available);


-- ============================================================
-- 3. ORDERS SERVICE
-- Owns carts, orders and group orders.
--
-- user_id, restaurant_id, item_id and location_id are external
-- service identifiers. They are intentionally NOT foreign keys.
--
-- order_items stores historical item_name and unit_price snapshots.
-- This prevents future catalogue changes from changing old orders.
-- ============================================================

CREATE TABLE orders.carts (
    cart_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT NOT NULL,
    restaurant_id   BIGINT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'CHECKED_OUT', 'ABANDONED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders.cart_items (
    cart_item_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cart_id         BIGINT NOT NULL
                    REFERENCES orders.carts(cart_id) ON DELETE CASCADE,
    item_id         BIGINT NOT NULL,
    quantity        INTEGER NOT NULL
                    CHECK (quantity > 0),
    added_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (cart_id, item_id)
);

CREATE TABLE orders.group_orders (
    group_order_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    owner_user_id   BIGINT NOT NULL,
    restaurant_id   BIGINT NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'OPEN'
                    CHECK (status IN ('OPEN', 'LOCKED', 'PLACED', 'CANCELLED', 'COMPLETED')),
    join_deadline   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orders.group_members (
    group_order_id  BIGINT NOT NULL
                    REFERENCES orders.group_orders(group_order_id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL,
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'LEFT')),
    PRIMARY KEY (group_order_id, user_id)
);

CREATE TABLE orders.orders (
    order_id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id                 BIGINT NOT NULL,
    restaurant_id           BIGINT NOT NULL,
    location_id             BIGINT,
    group_order_id          BIGINT,
    fulfilment_type         VARCHAR(20) NOT NULL
                            CHECK (fulfilment_type IN ('PICKUP', 'DELIVERY')),
    scheduled_at            TIMESTAMPTZ,
    status                  VARCHAR(30) NOT NULL DEFAULT 'PENDING_PAYMENT'
                            CHECK (
                                status IN (
                                    'PENDING_PAYMENT',
                                    'PLACED',
                                    'ACCEPTED',
                                    'PREPARING',
                                    'READY',
                                    'OUT_FOR_DELIVERY',
                                    'READY_FOR_PICKUP',
                                    'COMPLETED',
                                    'CANCELLED',
                                    'PAYMENT_FAILED'
                                )
                            ),
    subtotal                NUMERIC(10,2) NOT NULL
                            CHECK (subtotal >= 0),
    total                   NUMERIC(10,2) NOT NULL
                            CHECK (total >= 0),
    payment_reference       VARCHAR(150),
    fulfilment_reference    VARCHAR(150),
    idempotency_key         VARCHAR(100) NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, idempotency_key),

FOREIGN KEY (group_order_id)
    REFERENCES orders.group_orders(group_order_id)
    ON DELETE SET NULL,

CHECK (
    (fulfilment_type = 'DELIVERY' AND location_id IS NOT NULL)
    OR
    (fulfilment_type = 'PICKUP' AND location_id IS NULL)
)
);

CREATE TABLE orders.order_items (
    order_item_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id         BIGINT NOT NULL
                     REFERENCES orders.orders(order_id) ON DELETE CASCADE,
    item_id          BIGINT NOT NULL,
    item_name        VARCHAR(150) NOT NULL,
    quantity         INTEGER NOT NULL
                     CHECK (quantity > 0),
    unit_price       NUMERIC(10,2) NOT NULL
                     CHECK (unit_price >= 0),
    subtotal         NUMERIC(10,2) NOT NULL
                     CHECK (subtotal >= 0),
    UNIQUE (order_id, item_id)
);

CREATE INDEX idx_carts_user_status
    ON orders.carts(user_id, status);

CREATE INDEX idx_cart_items_cart
    ON orders.cart_items(cart_id);

CREATE INDEX idx_group_orders_owner
    ON orders.group_orders(owner_user_id);

CREATE INDEX idx_group_members_user
    ON orders.group_members(user_id);

CREATE INDEX idx_orders_user
    ON orders.orders(user_id);

CREATE INDEX idx_orders_restaurant
    ON orders.orders(restaurant_id);

CREATE INDEX idx_orders_status
    ON orders.orders(status);

CREATE INDEX idx_orders_scheduled
    ON orders.orders(scheduled_at);

CREATE INDEX idx_orders_group
    ON orders.orders(group_order_id);

CREATE INDEX idx_order_items_order
    ON orders.order_items(order_id);


-- ============================================================
-- 4. PAYMENTS SERVICE
-- Owns payment methods, payments, transactions and refunds.
--
-- Raw card numbers and CVV are NOT stored.
-- provider_token_ref represents a token/reference managed by
-- an external payment provider.
-- ============================================================

CREATE TABLE payments.payment_methods (
    payment_method_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id              BIGINT NOT NULL,
    method_type          VARCHAR(30) NOT NULL
                         CHECK (method_type IN ('CARD', 'UPI', 'WALLET')),
    provider_token_ref   VARCHAR(255) NOT NULL UNIQUE,
    last4                CHAR(4),
    status               VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                         CHECK (status IN ('ACTIVE', 'INACTIVE')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payments.payments (
    payment_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id             BIGINT NOT NULL,
    user_id              BIGINT NOT NULL,
    amount               NUMERIC(10,2) NOT NULL
                         CHECK (amount > 0),
    currency             CHAR(3) NOT NULL DEFAULT 'INR',
    status               VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                         CHECK (
                             status IN (
                                 'PENDING',
                                 'AUTHORIZED',
                                 'CAPTURED',
                                 'FAILED',
                                 'REFUNDED',
                                 'PARTIALLY_REFUNDED'
                             )
                         ),
    provider_reference   VARCHAR(255),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payments.transactions (
    transaction_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payment_id           BIGINT NOT NULL
                         REFERENCES payments.payments(payment_id) ON DELETE CASCADE,
    transaction_type     VARCHAR(30) NOT NULL
                         CHECK (transaction_type IN ('AUTHORIZATION', 'CAPTURE', 'VOID', 'REFUND')),
    amount               NUMERIC(10,2) NOT NULL
                         CHECK (amount >= 0),
    status               VARCHAR(20) NOT NULL
                         CHECK (status IN ('PENDING', 'SUCCESS', 'FAILED')),
    provider_reference   VARCHAR(255),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE payments.refunds (
    refund_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    payment_id           BIGINT NOT NULL
                         REFERENCES payments.payments(payment_id) ON DELETE CASCADE,
    amount               NUMERIC(10,2) NOT NULL
                         CHECK (amount > 0),
    reason               VARCHAR(255),
    status               VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                         CHECK (status IN ('PENDING', 'SUCCESS', 'FAILED')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payment_methods_user
    ON payments.payment_methods(user_id);

CREATE INDEX idx_payments_order
    ON payments.payments(order_id);

CREATE INDEX idx_payments_user
    ON payments.payments(user_id);

CREATE INDEX idx_payments_status
    ON payments.payments(status);

CREATE INDEX idx_transactions_payment
    ON payments.transactions(payment_id);

CREATE INDEX idx_refunds_payment
    ON payments.refunds(payment_id);


-- ============================================================
-- 5. DELIVERY SERVICE
-- Owns fulfilment and delivery assignments.
--
-- order_id, location_id, pickup_point_id and rider_user_id are
-- external identifiers and are intentionally NOT foreign keys.
-- ============================================================

CREATE TABLE delivery.fulfilments (
    fulfilment_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id            BIGINT NOT NULL UNIQUE,
    fulfilment_type     VARCHAR(20) NOT NULL
                        CHECK (fulfilment_type IN ('PICKUP', 'DELIVERY')),
    location_id         BIGINT,
    pickup_point_id     BIGINT,
    status              VARCHAR(30) NOT NULL DEFAULT 'CREATED'
                        CHECK (
                            status IN (
                                'CREATED',
                                'ASSIGNMENT_PENDING',
                                'ASSIGNED',
                                'READY',
                                'PICKED_UP',
                                'OUT_FOR_DELIVERY',
                                'READY_FOR_PICKUP',
                                'COMPLETED',
                                'CANCELLED'
                            )
                        ),
    scheduled_for       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (fulfilment_type = 'DELIVERY'
            AND location_id IS NOT NULL
            AND pickup_point_id IS NULL)
        OR
        (fulfilment_type = 'PICKUP'
            AND location_id IS NULL
            AND pickup_point_id IS NOT NULL)
    )
);

CREATE TABLE delivery.delivery_assignments (
    assignment_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fulfilment_id       BIGINT NOT NULL
                         REFERENCES delivery.fulfilments(fulfilment_id) ON DELETE CASCADE,
    rider_user_id       BIGINT NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'ASSIGNED'
                         CHECK (status IN ('ASSIGNED', 'ACCEPTED', 'PICKED_UP', 'DELIVERED', 'CANCELLED')),
    assigned_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    picked_up_at        TIMESTAMPTZ,
    delivered_at        TIMESTAMPTZ
);

CREATE INDEX idx_fulfilments_order
    ON delivery.fulfilments(order_id);

CREATE INDEX idx_fulfilments_status
    ON delivery.fulfilments(status);

CREATE INDEX idx_fulfilments_scheduled
    ON delivery.fulfilments(scheduled_for);

CREATE INDEX idx_delivery_assignments_fulfilment
    ON delivery.delivery_assignments(fulfilment_id);

CREATE INDEX idx_delivery_assignments_rider
    ON delivery.delivery_assignments(rider_user_id);


-- ============================================================
-- 6. CAMPUS ENGAGEMENT SERVICE
-- Owns notifications and reviews.
--
-- user_id, order_id, restaurant_id and item_id are external
-- service identifiers and are intentionally NOT foreign keys.
-- ============================================================

CREATE TABLE campus_engagement.notifications (
    notification_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT NOT NULL,
    event_type          VARCHAR(50) NOT NULL,
    channel             VARCHAR(20) NOT NULL
                        CHECK (channel IN ('IN_APP', 'EMAIL', 'SMS')),
    title               VARCHAR(200) NOT NULL,
    message             TEXT NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'UNREAD'
                        CHECK (status IN ('UNREAD', 'READ', 'FAILED')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at             TIMESTAMPTZ
);

CREATE TABLE campus_engagement.restaurant_reviews (
    review_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT NOT NULL,
    order_id            BIGINT NOT NULL,
    restaurant_id       BIGINT NOT NULL,
    rating              SMALLINT NOT NULL
                        CHECK (rating BETWEEN 1 AND 5),
    comment             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, order_id, restaurant_id)
);

CREATE TABLE campus_engagement.item_reviews (
    review_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id             BIGINT NOT NULL,
    order_id            BIGINT NOT NULL,
    item_id             BIGINT NOT NULL,
    rating              SMALLINT NOT NULL
                        CHECK (rating BETWEEN 1 AND 5),
    comment             TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, order_id, item_id)
);

CREATE INDEX idx_notifications_user
    ON campus_engagement.notifications(user_id);

CREATE INDEX idx_notifications_status
    ON campus_engagement.notifications(status);

CREATE INDEX idx_restaurant_reviews_restaurant
    ON campus_engagement.restaurant_reviews(restaurant_id);

CREATE INDEX idx_restaurant_reviews_user
    ON campus_engagement.restaurant_reviews(user_id);

CREATE INDEX idx_item_reviews_item
    ON campus_engagement.item_reviews(item_id);

CREATE INDEX idx_item_reviews_user
    ON campus_engagement.item_reviews(user_id);

COMMIT;
