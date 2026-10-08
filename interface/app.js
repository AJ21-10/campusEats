const API_BASE = window.CAMPUS_EATS_API_BASE || `${window.location.protocol}//${window.location.hostname || 'localhost'}:8000`;
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
    const user = JSON.parse(raw);
    return user && Number.isInteger(Number(user.user_id)) && Number(user.user_id) > 0
      ? { ...user, user_id: Number(user.user_id) }
      : { user_id: null, email: 'Guest' };
  } catch {
    return { user_id: null, email: 'Guest' };
  }
}

function saveCurrentUser(user) {
  const current = getCurrentUser();
  if (current.user_id && current.user_id !== Number(user.user_id)) {
    localStorage.removeItem(STORAGE_KEYS.cart);
  }
  localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(user));
}

function getCart() {
  const raw = localStorage.getItem(STORAGE_KEYS.cart);
  if (!raw) return [];
  try {
    const cart = JSON.parse(raw);
    return Array.isArray(cart)
      ? cart.filter((item) => Number.isInteger(Number(item.item_id)) && Number(item.quantity) > 0)
      : [];
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

  const navLinks = document.querySelector('.nav-links');
  if (navLinks) {
    let logout = document.getElementById('logoutButton');
    if (user.user_id && !logout) {
      logout = document.createElement('button');
      logout.id = 'logoutButton';
      logout.className = 'secondary-btn';
      logout.type = 'button';
      logout.textContent = 'Logout';
      logout.addEventListener('click', () => {
        localStorage.removeItem(STORAGE_KEYS.user);
        window.location.href = 'index.html';
      });
      navLinks.append(logout);
    } else if (!user.user_id && logout) {
      logout.remove();
    }
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

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      method: options.method || 'GET',
      headers,
    });
  } catch {
    throw new Error(`Cannot reach the CampusEats API at ${API_BASE}. Make sure the API is running.`);
  }

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      throw new Error(`The API returned an unreadable response (${response.status}).`);
    }
  }

  if (!response.ok) {
    const validationDetails = Array.isArray(payload?.errors)
      ? payload.errors.map((item) => `${item.field}: ${item.reason}`).join('; ')
      : null;
    throw new Error(validationDetails || payload?.detail || payload?.title || payload?.message || `Request failed with ${response.status}`);
  }

  return payload;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[character]);
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

async function handleRegister(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const password = String(data.get('password') || '');
  const confirmPassword = String(data.get('confirm_password') || '');
  const status = document.getElementById('registerStatus');
  const submitButton = form.querySelector('[type="submit"]');

  if (password !== confirmPassword) {
    setStatus(status, 'Passwords do not match.', 'error');
    return;
  }

  const payload = {
    full_name: String(data.get('full_name') || '').trim(),
    email: String(data.get('email') || '').trim(),
    phone: String(data.get('phone') || '').trim() || null,
    password,
    role: 'STUDENT',
  };

  if (!payload.full_name || !payload.email || password.length < 8) {
    setStatus(status, 'Enter a name, a valid email, and a password with at least 8 characters.', 'error');
    return;
  }

  if (submitButton) submitButton.disabled = true;
  try {
    const result = await apiRequest('/accounts/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (!result?.user_id || result.status !== 'ACTIVE') {
      throw new Error('Account was created, but automatic sign-in was not available. Please log in.');
    }

    saveCurrentUser({
      user_id: Number(result.user_id),
      email: result.email || payload.email,
      role: result.role || 'STUDENT',
    });
    form.reset();
    updateNavUser();
    setStatus(status, 'Account created. You are now signed in.', 'success');
    window.setTimeout(() => {
      window.location.href = 'catalog.html';
    }, 700);
  } catch (error) {
    setStatus(status, error.message || 'Unable to create your account.', 'error');
  } finally {
    if (submitButton) submitButton.disabled = false;
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
    const result = await apiRequest('/accounts/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
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
              <h3>${escapeHtml(restaurant.name)}</h3>
              <span class="status-badge">${escapeHtml(restaurant.status)}</span>
            </div>
            <p>Campus ${escapeHtml(restaurant.campus_id)}</p>
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
    const restaurant = (await apiRequest('/catalogue/restaurants')).find((entry) => Number(entry.restaurant_id) === Number(restaurantId)) || { name: 'Restaurant', campus_id: 'N/A', status: 'ACTIVE' };

    if (restaurantNameEl) restaurantNameEl.textContent = restaurant.name;
    if (restaurantMetaEl) {
      restaurantMetaEl.innerHTML = `
        <span>Campus: ${escapeHtml(restaurant.campus_id)}</span>
        <span>Status: ${escapeHtml(restaurant.status)}</span>
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
              <h3>${escapeHtml(item.name)}</h3>
              <p>${escapeHtml(item.description || 'Freshly prepared campus favorite')}</p>
              <div class="menu-meta">
                <span>${item.is_available ? 'Available' : 'Unavailable'}</span>
                <span>${formatCurrency(item.price)}</span>
              </div>
            </div>
            <button class="primary-btn add-to-cart" data-item-id="${item.item_id}" data-item-name="${escapeHtml(item.name)}" data-item-price="${item.price}" ${item.is_available ? '' : 'disabled'}>
              Add to cart
            </button>
          </div>
        `,
      )
      .join('');

    menuListEl.querySelectorAll('.add-to-cart').forEach((button) => {
      button.addEventListener('click', async () => {
        const itemId = Number(button.dataset.itemId);
        const itemName = button.dataset.itemName;
        const itemPrice = Number(button.dataset.itemPrice);

        const currentCart = getCart();
        const existingRestaurantId = currentCart[0]?.restaurant_id;
        if (existingRestaurantId && Number(existingRestaurantId) !== Number(restaurantId)) {
          setStatus(menuStatusEl, 'Your cart already has items from another restaurant. Empty it before switching restaurants.', 'error');
          return;
        }
        const existing = currentCart.find((entry) => entry.item_id === itemId);
        button.disabled = true;
        try {
          await apiRequest('/orders/cart/items', {
            method: 'POST',
            body: JSON.stringify({ user_id: getCurrentUser().user_id, item_id: itemId, quantity: 1 }),
          });
          if (existing) {
            existing.quantity += 1;
          } else {
            currentCart.push({
              item_id: itemId,
              name: itemName,
              price: itemPrice,
              quantity: 1,
              restaurant_id: Number(restaurantId),
            });
          }
          saveCart(currentCart);
          updateNavUser();
          setStatus(menuStatusEl, `${itemName} added to cart`, 'success');
          showToast(`${itemName} added to your cart`);
        } catch (error) {
          setStatus(menuStatusEl, error.message || 'Unable to add item to cart', 'error');
        } finally {
          button.disabled = false;
        }
      });
    });

    setStatus(menuStatusEl, `${items.length} items available`, 'success');
  } catch (error) {
    setStatus(menuStatusEl, error.message || 'Unable to load menu', 'error');
  }
}

async function loadCheckoutOptions() {
  const user = getCurrentUser();
  const paymentSelect = document.getElementById('paymentMethodId');
  const locationSelect = document.getElementById('locationId');
  const cartStatus = document.getElementById('cartStatus');
  if (!user.user_id || !paymentSelect || !locationSelect) return;

  try {
    const [methods, locations] = await Promise.all([
      apiRequest(`/payments/methods?user_id=${user.user_id}`),
      apiRequest(`/accounts/${user.user_id}/locations`),
    ]);
    paymentSelect.innerHTML = methods.length
      ? methods.map((method) => {
        const suffix = method.last4 ? ` •••• ${escapeHtml(method.last4)}` : '';
        return `<option value="${method.payment_method_id}">${escapeHtml(method.method_type)}${suffix}</option>`;
      }).join('')
      : '<option value="1">Demo order — payment remains pending</option>';
    paymentSelect.disabled = false;

    locationSelect.innerHTML = locations.length
      ? locations.map((location) => {
        const room = location.room ? `, ${escapeHtml(location.room)}` : '';
        const defaultLabel = location.is_default ? ' (default)' : '';
        return `<option value="${location.location_id}">${escapeHtml(location.label)} — ${escapeHtml(location.building)}${room}${defaultLabel}</option>`;
      }).join('')
      : '<option value="">No saved delivery locations</option>';
    if (!locations.length) {
      setStatus(cartStatus, 'No saved delivery location is available for delivery. Choose pickup or add a location to your account.', 'info');
    }
  } catch (error) {
    paymentSelect.innerHTML = '<option value="">Unable to load payment methods</option>';
    locationSelect.innerHTML = '<option value="">Unable to load saved locations</option>';
    setStatus(cartStatus, error.message || 'Unable to load checkout options', 'error');
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
            <strong>${escapeHtml(item.name)}</strong>
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
    button.addEventListener('click', async () => {
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
  const form = event.currentTarget;
  const cartStatus = document.getElementById('cartStatus');

  if (!user.user_id) {
    window.location.href = 'login.html';
    return;
  }

  if (!cart.length) {
    setStatus(cartStatus, 'Add at least one item before placing an order.', 'error');
    return;
  }

  const fulfilmentType = document.getElementById('fulfilmentType').value;
  const paymentMethodId = Number(document.getElementById('paymentMethodId').value || 1);
  const locationId = Number(document.getElementById('locationId').value);
  if (fulfilmentType === 'DELIVERY' && !locationId) {
    setStatus(cartStatus, 'Choose a saved delivery location or select pickup.', 'error');
    return;
  }

  const itemFingerprint = cart
    .map((item) => `${Number(item.item_id)}x${Number(item.quantity)}`)
    .sort()
    .join(',');
  const fingerprint = `${user.user_id}:${fulfilmentType}:${locationId || 0}:${itemFingerprint}`;
  const idempotencyStorageKey = 'campuseats_checkout_request';
  let previousRequest;
  try {
    previousRequest = JSON.parse(localStorage.getItem(idempotencyStorageKey) || 'null');
  } catch {
    previousRequest = null;
  }
  const idempotencyKey = previousRequest?.fingerprint === fingerprint
    ? previousRequest.key
    : `ui-${user.user_id}-${crypto.randomUUID()}`;
  localStorage.setItem(idempotencyStorageKey, JSON.stringify({ fingerprint, key: idempotencyKey }));

  const submitButton = form.querySelector('[type="submit"]');
  if (submitButton) submitButton.disabled = true;
  try {
    const payload = {
      user_id: user.user_id,
      items: cart.map((item) => ({ item_id: item.item_id, quantity: item.quantity })),
      payment_method_id: paymentMethodId,
      fulfilment_type: fulfilmentType,
      location_id: fulfilmentType === 'DELIVERY' ? locationId : null,
      idempotency_key: idempotencyKey,
    };

    const result = await apiRequest('/orders', {
      method: 'POST',
      headers: {
        'Idempotency-Key': payload.idempotency_key,
      },
      body: JSON.stringify(payload),
    });

    localStorage.setItem(STORAGE_KEYS.lastOrder, JSON.stringify(result));
    localStorage.removeItem(idempotencyStorageKey);
    saveCart([]);
    updateNavUser();
    renderCartPage();
    setStatus(cartStatus, 'Order placed successfully.', 'success');
    window.location.href = 'orders.html';
  } catch (error) {
    setStatus(cartStatus, error.message || 'Failed to place order', 'error');
  } finally {
    if (submitButton) submitButton.disabled = false;
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
        <p><strong>Status:</strong> ${escapeHtml(details.status)}</p>
        <p><strong>Restaurant ID:</strong> ${escapeHtml(details.restaurant_id)}</p>
        <p><strong>Fulfilment:</strong> ${escapeHtml(details.fulfilment_type)}</p>
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

  if (page === 'register') {
    const form = document.getElementById('registerForm');
    form?.addEventListener('submit', handleRegister);
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
    loadCheckoutOptions();
    const fulfilmentType = document.getElementById('fulfilmentType');
    const deliveryField = document.getElementById('deliveryLocationField');
    const locationId = document.getElementById('locationId');
    const updateDeliveryField = () => {
      const deliverySelected = fulfilmentType?.value === 'DELIVERY';
      if (deliveryField) deliveryField.hidden = !deliverySelected;
      if (locationId) locationId.required = Boolean(deliverySelected);
    };
    fulfilmentType?.addEventListener('change', updateDeliveryField);
    updateDeliveryField();
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
