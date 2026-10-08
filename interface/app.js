const API_BASE = 'http://localhost:8000';
const STORAGE_KEYS = {
  user: 'campuseats_user',
  cart: 'campuseats_cart',
  selectedRestaurant: 'campuseats_selected_restaurant',
  lastOrder: 'campuseats_last_order',
};

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function getCurrentUser() {
  const raw = localStorage.getItem(STORAGE_KEYS.user);
  if (!raw) {
    return { user_id: null, email: 'Guest' };
  }
  try {
    return JSON.parse(raw);
  } catch {
    return { user_id: null, email: 'Guest' };
  }
}

function saveCurrentUser(user) {
  localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
}

function getCart() {
  const raw = localStorage.getItem(STORAGE_KEYS.cart);
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function saveCart(cart) {
  localStorage.setItem(STORAGE_KEYS.cart, JSON.stringify(cart));
}

function updateNavUser() {
  const user = getCurrentUser();
  const cartCount = getCart().reduce((sum, item) => sum + item.quantity, 0);
  const navUsers = document.querySelectorAll('#navUser');
  navUsers.forEach((el) => {
    el.textContent = user.user_id ? user.email : 'Guest';
  });

  document.querySelectorAll('.nav-links a[href="cart.html"]').forEach((link) => {
    let badge = link.querySelector('.nav-cart-count');
    if (cartCount && !badge) {
      badge = document.createElement('span');
      badge.className = 'nav-cart-count';
      link.append(badge);
    }
    if (badge) {
      badge.textContent = String(cartCount);
      badge.hidden = cartCount === 0;
    }
  });

  const currentPage = window.location.pathname.split('/').pop() || 'index.html';
  document.querySelectorAll('.nav-links a').forEach((link) => {
    if (link.getAttribute('href') === currentPage) {
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
    }
  });

  const heroName = document.getElementById('heroUserName');
  if (heroName) {
    heroName.textContent = user.user_id ? user.email : 'Guest';
  }

  const heroCartCount = document.getElementById('heroCartCount');
  if (heroCartCount) {
    heroCartCount.textContent = String(cartCount);
  }
}

function showToast(message) {
  let toast = document.querySelector('.toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    document.body.append(toast);
  }
  toast.textContent = message;
  toast.classList.add('visible');
  window.clearTimeout(showToast.timeoutId);
  showToast.timeoutId = window.setTimeout(() => toast.classList.remove('visible'), 2200);
}

function getAuthorizationHeaders(extra = {}) {
  const user = getCurrentUser();
  return {
    Accept: 'application/json',
    Authorization: user.user_id ? 'Bearer demo-token' : 'Bearer demo-token',
    ...extra,
  };
}

async function apiRequest(path, options = {}) {
  const headers = {
    ...getAuthorizationHeaders(),
    ...(options.headers || {}),
  };

  if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method: options.method || 'GET',
    ...options,
    headers,
  });

  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const detail = payload?.detail ?? payload?.message ?? payload?.error ?? `Request failed with ${response.status}`;
    throw new Error(detail);
  }

  return payload;
}

function setStatus(el, message, type = 'info') {
  if (!el) return;
  el.textContent = message;
  el.className = `status-box ${type}`;
}

function redirectIfNeeded() {
  const user = getCurrentUser();
  const page = document.body.dataset.page;
  if ((page === 'catalog' || page === 'restaurant' || page === 'cart' || page === 'orders') && !user.user_id) {
    window.location.href = 'login.html';
  }
}

async function handleLogin(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const email = data.get('email');
  const password = data.get('password');
  const status = document.getElementById('loginStatus');

  try {
    const result = await apiRequest(`/accounts/login?email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`, {
      method: 'POST',
    });

    if (result && result.user_id) {
      saveCurrentUser({ user_id: Number(result.user_id), email: result.email || email });
      updateNavUser();
      setStatus(status, 'Login successful. Redirecting…', 'success');
      setTimeout(() => window.location.href = 'catalog.html', 600);
    } else {
      throw new Error('Login failed');
    }
  } catch (error) {
    setStatus(status, error.message || 'Login failed', 'error');
  }
}

async function loadRestaurants() {
  const statusEl = document.getElementById('catalogStatus');
  const cardsEl = document.getElementById('restaurantCards');

  if (!cardsEl || !statusEl) return;

  try {
    const restaurants = await apiRequest('/catalogue/restaurants');
    const searchValue = (document.getElementById('restaurantSearch')?.value || '').trim().toLowerCase();
    const filtered = restaurants.filter((restaurant) => {
      if (!searchValue) return true;
      return restaurant.name.toLowerCase().includes(searchValue);
    });

    if (!filtered.length) {
      cardsEl.innerHTML = '<div class="empty-state">No restaurants match your search.</div>';
      setStatus(statusEl, 'No results found', 'info');
      return;
    }

    cardsEl.innerHTML = filtered
      .map(
        (restaurant) => `
          <article class="restaurant-card panel-card">
            <div class="restaurant-header">
              <h3>${restaurant.name}</h3>
              <span class="status-badge">${restaurant.status}</span>
            </div>
            <p>Campus ${restaurant.campus_id}</p>
            <div class="restaurant-actions">
              <button class="secondary-btn" data-restaurant-id="${restaurant.restaurant_id}">View menu</button>
            </div>
          </article>
        `,
      )
      .join('');

    cardsEl.querySelectorAll('[data-restaurant-id]').forEach((button) => {
      button.addEventListener('click', () => {
        const id = Number(button.dataset.restaurantId);
        localStorage.setItem(STORAGE_KEYS.selectedRestaurant, JSON.stringify({ restaurant_id: id }));
        window.location.href = `restaurant.html?restaurant_id=${id}`;
      });
    });

    setStatus(statusEl, `Loaded ${filtered.length} restaurants`, 'success');
  } catch (error) {
    setStatus(statusEl, error.message || 'Unable to load restaurants', 'error');
    cardsEl.innerHTML = '<div class="empty-state">Unable to load restaurant list.</div>';
  }
}

function getSelectedRestaurantId() {
  const params = new URLSearchParams(window.location.search);
  if (params.get('restaurant_id')) return Number(params.get('restaurant_id'));

  const raw = localStorage.getItem(STORAGE_KEYS.selectedRestaurant);
  if (raw) {
    try {
      return Number(JSON.parse(raw).restaurant_id);
    } catch {
      return null;
    }
  }
  return null;
}

async function loadRestaurantPage() {
  const restaurantId = getSelectedRestaurantId();
  const restaurantNameEl = document.getElementById('restaurantName');
  const restaurantMetaEl = document.getElementById('restaurantMeta');
  const menuStatusEl = document.getElementById('menuStatus');
  const menuListEl = document.getElementById('menuList');

  if (!restaurantId) {
    setStatus(menuStatusEl, 'No restaurant selected', 'error');
    menuListEl.innerHTML = '<div class="empty-state">Select a restaurant from the catalogue first.</div>';
    if (restaurantNameEl) restaurantNameEl.textContent = 'Restaurant not found';
    return;
  }

  try {
    const items = await apiRequest(`/catalogue/restaurants/${restaurantId}/menu`);
    const restaurant = (await apiRequest('/catalogue/restaurants')).find((entry) => entry.restaurant_id === restaurantId) || { name: 'Restaurant', campus_id: 'N/A', status: 'ACTIVE' };

    if (restaurantNameEl) restaurantNameEl.textContent = restaurant.name;
    if (restaurantMetaEl) {
      restaurantMetaEl.innerHTML = `
        <span>Campus: ${restaurant.campus_id}</span>
        <span>Status: ${restaurant.status}</span>
        <span>Items: ${items.length}</span>
      `;
    }

    if (!items.length) {
      setStatus(menuStatusEl, 'This restaurant has no menu items yet', 'info');
      menuListEl.innerHTML = '<div class="empty-state">No items available.</div>';
      return;
    }

    menuListEl.innerHTML = items
      .map(
        (item) => `
          <div class="menu-item-card">
            <div>
              <h3>${item.name}</h3>
              <p>${item.description || 'Freshly prepared campus favorite'}</p>
              <div class="menu-meta">
                <span>${item.is_available ? 'Available' : 'Unavailable'}</span>
                <span>${formatCurrency(item.price)}</span>
              </div>
            </div>
            <button class="primary-btn add-to-cart" data-item-id="${item.item_id}" data-item-name="${item.name}" data-item-price="${item.price}">
              Add to cart
            </button>
          </div>
        `,
      )
      .join('');

    menuListEl.querySelectorAll('.add-to-cart').forEach((button) => {
      button.addEventListener('click', () => {
        const itemId = Number(button.dataset.itemId);
        const itemName = button.dataset.itemName;
        const itemPrice = Number(button.dataset.itemPrice);

        const currentCart = getCart();
        const existing = currentCart.find((entry) => entry.item_id === itemId);
        if (existing) {
          existing.quantity += 1;
        } else {
          currentCart.push({ item_id: itemId, name: itemName, price: itemPrice, quantity: 1 });
        }
        saveCart(currentCart);
        updateNavUser();
        setStatus(menuStatusEl, `${itemName} added to cart`, 'success');
        showToast(`${itemName} added to your cart`);
      });
    });

    setStatus(menuStatusEl, `${items.length} items available`, 'success');
  } catch (error) {
    setStatus(menuStatusEl, error.message || 'Unable to load menu', 'error');
  }
}

function renderCartPage() {
  const cartItemsEl = document.getElementById('cartItems');
  const cartSubtotalEl = document.getElementById('cartSubtotal');
  const cartTotalEl = document.getElementById('cartTotal');
  const cartStatusEl = document.getElementById('cartStatus');

  if (!cartItemsEl || !cartSubtotalEl || !cartTotalEl || !cartStatusEl) return;

  const cart = getCart();
  if (!cart.length) {
    cartItemsEl.innerHTML = '<div class="empty-state">No items in your cart yet.</div>';
    cartSubtotalEl.textContent = formatCurrency(0);
    cartTotalEl.textContent = formatCurrency(0);
    setStatus(cartStatusEl, 'Cart is empty.', 'info');
    return;
  }

  const subtotal = cart.reduce((sum, item) => sum + item.price * item.quantity, 0);
  cartItemsEl.innerHTML = cart
    .map(
      (item) => `
        <div class="cart-item-row">
          <div>
            <strong>${item.name}</strong>
            <div class="menu-meta">${formatCurrency(item.price)} each</div>
          </div>
          <div class="qty-controls">
            <button class="qty-btn" data-action="decrease" data-item-id="${item.item_id}">-</button>
            <span>${item.quantity}</span>
            <button class="qty-btn" data-action="increase" data-item-id="${item.item_id}">+</button>
            <button class="remove-btn" data-action="remove" data-item-id="${item.item_id}">Remove</button>
          </div>
        </div>
      `,
    )
    .join('');

  cartSubtotalEl.textContent = formatCurrency(subtotal);
  cartTotalEl.textContent = formatCurrency(subtotal);
  setStatus(cartStatusEl, `${cart.length} item(s) ready to checkout`, 'success');

  cartItemsEl.querySelectorAll('[data-action]').forEach((button) => {
    button.addEventListener('click', () => {
      const itemId = Number(button.dataset.itemId);
      const action = button.dataset.action;
      const updated = getCart();
      const target = updated.find((entry) => entry.item_id === itemId);
      if (!target) return;

      if (action === 'increase') target.quantity += 1;
      if (action === 'decrease') target.quantity -= 1;
      if (action === 'remove' || target.quantity <= 0) {
        const filtered = updated.filter((entry) => entry.item_id !== itemId);
        saveCart(filtered);
        renderCartPage();
        updateNavUser();
        return;
      }

      saveCart(updated);
      renderCartPage();
      updateNavUser();
      showToast(action === 'increase' ? 'Quantity updated' : 'Item quantity reduced');
    });
  });
}

async function placeOrderFromCart(event) {
  event.preventDefault();
  const user = getCurrentUser();
  const cart = getCart();

  if (!user.user_id) {
    window.location.href = 'login.html';
    return;
  }

  if (!cart.length) {
    setStatus(document.getElementById('cartStatus'), 'Add at least one item before placing an order.', 'error');
    return;
  }

  try {
    const payload = {
      user_id: user.user_id,
      items: cart.map((item) => ({ item_id: item.item_id, quantity: item.quantity })),
      payment_method_id: Number(document.getElementById('paymentMethodId').value || 1),
      fulfilment_type: document.getElementById('fulfilmentType').value,
      idempotency_key: `campuseats-${Date.now()}`,
    };

    const result = await apiRequest('/orders', {
      method: 'POST',
      headers: {
        'Idempotency-Key': payload.idempotency_key,
      },
      body: JSON.stringify(payload),
    });

    localStorage.setItem(STORAGE_KEYS.lastOrder, JSON.stringify(result));
    saveCart([]);
    updateNavUser();
    renderCartPage();
    setStatus(document.getElementById('cartStatus'), 'Order placed successfully.', 'success');
    window.location.href = 'orders.html';
  } catch (error) {
    setStatus(document.getElementById('cartStatus'), error.message || 'Failed to place order', 'error');
  }
}

async function loadOrdersPage() {
  const ordersStatusEl = document.getElementById('ordersStatus');
  const orderDetailsEl = document.getElementById('orderDetails');
  const user = getCurrentUser();

  if (!user.user_id) {
    window.location.href = 'login.html';
    return;
  }

  const lastOrderRaw = localStorage.getItem(STORAGE_KEYS.lastOrder);
  if (!lastOrderRaw) {
    setStatus(ordersStatusEl, 'No order loaded yet', 'info');
    orderDetailsEl.innerHTML = '<div class="empty-state">Place an order from the cart to see it here.</div>';
    return;
  }

  try {
    const order = JSON.parse(lastOrderRaw);
    const details = await apiRequest(`/orders/${order.order_id}?user_id=${user.user_id}`);
    orderDetailsEl.innerHTML = `
      <div class="order-card">
        <h3>Order #${details.order_id}</h3>
        <p><strong>Status:</strong> ${details.status}</p>
        <p><strong>Restaurant ID:</strong> ${details.restaurant_id}</p>
        <p><strong>Fulfilment:</strong> ${details.fulfilment_type}</p>
        <p><strong>Total:</strong> ${formatCurrency(details.total)}</p>
      </div>
    `;
    setStatus(ordersStatusEl, 'Latest order loaded', 'success');
  } catch (error) {
    setStatus(ordersStatusEl, error.message || 'Unable to load order', 'error');
  }
}

function bindGlobalUI() {
  const page = document.body.dataset.page;
  updateNavUser();

  if (page === 'login') {
    const form = document.getElementById('loginForm');
    form?.addEventListener('submit', handleLogin);
  }

  if (page === 'catalog') {
    const search = document.getElementById('restaurantSearch');
    search?.addEventListener('input', loadRestaurants);
    const refreshBtn = document.getElementById('refreshCatalogBtn');
    refreshBtn?.addEventListener('click', loadRestaurants);
    loadRestaurants();
  }

  if (page === 'restaurant') {
    loadRestaurantPage();
  }

  if (page === 'cart') {
    renderCartPage();
    const checkoutForm = document.getElementById('checkoutForm');
    checkoutForm?.addEventListener('submit', placeOrderFromCart);
  }

  if (page === 'orders') {
    loadOrdersPage();
    const refreshBtn = document.getElementById('refreshOrderBtn');
    refreshBtn?.addEventListener('click', loadOrdersPage);
  }

  if (page === 'home') {
    updateNavUser();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  redirectIfNeeded();
  bindGlobalUI();
});
