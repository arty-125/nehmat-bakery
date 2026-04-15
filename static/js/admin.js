/**
 * Nehmat Bakery — Admin Panel JavaScript
 * Handles: sidebar toggle • inline edit forms • delete confirm • drag-reorder
 */

'use strict';

// ── Sidebar mobile toggle ─────────────────────────────────────────────────────
(function initSidebar() {
  const toggle   = document.querySelector('.sidebar-toggle');
  const sidebar  = document.querySelector('.admin-sidebar');
  const overlay  = document.querySelector('.sidebar-overlay');
  if (!toggle || !sidebar) return;

  const open  = () => { sidebar.classList.add('open');  overlay?.classList.add('active');  document.body.style.overflow = 'hidden'; };
  const close = () => { sidebar.classList.remove('open'); overlay?.classList.remove('active'); document.body.style.overflow = ''; };

  toggle.addEventListener('click',  open);
  overlay?.addEventListener('click', close);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });
})();

// ── Flash message auto-dismiss ────────────────────────────────────────────────
(function initFlash() {
  document.querySelectorAll('.flash-item').forEach(msg => {
    setTimeout(() => {
      msg.style.transition = 'opacity .35s, transform .35s';
      msg.style.opacity    = '0';
      msg.style.transform  = 'translateY(-6px)';
      setTimeout(() => msg.remove(), 380);
    }, 4500);
  });
})();

// ── Product card expand/collapse ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.expand-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const form = btn.closest('.product-admin-card')?.querySelector('.product-edit-form');
      if (!form) return;
      const open = form.classList.toggle('open');
      btn.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', String(open));
      btn.title = open ? 'Collapse' : 'Edit';
    });
  });
});

// ── Slide inline edit toggle ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.slide-edit-toggle').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.slide-item');
      const form = item?.querySelector('.slide-edit-form');
      if (!form) return;
      const open = form.classList.toggle('open');
      btn.textContent = open ? 'Cancel' : 'Edit';
    });
  });
});

// ── Confirm before delete ─────────────────────────────────────────────────────
document.addEventListener('submit', e => {
  const form = e.target;
  if (!form.dataset.confirm) return;
  if (!window.confirm(form.dataset.confirm)) {
    e.preventDefault();
  }
});

// ── Drag-to-reorder (slider) ──────────────────────────────────────────────────
(function initDragSort() {
  const list = document.querySelector('#slide-list[data-sortable]');
  if (!list) return;

  let dragSrc = null;

  list.querySelectorAll('.slide-item[draggable]').forEach(item => {
    item.addEventListener('dragstart', e => {
      dragSrc = item;
      item.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
    });
    item.addEventListener('dragend', () => {
      item.classList.remove('dragging');
      dragSrc = null;
      _saveOrder(list);
    });
    item.addEventListener('dragover', e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (item === dragSrc) return;
      const rect     = item.getBoundingClientRect();
      const midY     = rect.top + rect.height / 2;
      const insertAfter = e.clientY > midY;
      if (insertAfter) {
        item.after(dragSrc);
      } else {
        item.before(dragSrc);
      }
    });
  });

  function _saveOrder(listEl) {
    const order = Array.from(listEl.querySelectorAll('.slide-item[draggable]'))
                       .map(el => el.dataset.id);
    const csrf  = document.querySelector('meta[name="csrf-token"]')?.content || '';

    fetch('/admin/slider/reorder', {
      method:  'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrf,   // custom header not read server-side here;
      },
      body: JSON.stringify({ order, csrf_token: csrf }),
    })
    .then(r => r.json())
    .then(d => {
      if (d.ok) _showToast('Order saved', 'success');
    })
    .catch(() => _showToast('Could not save order', 'danger'));
  }
})();

// ── File input label update ───────────────────────────────────────────────────
document.addEventListener('change', e => {
  const input = e.target;
  if (input.type !== 'file') return;
  const label = input.closest('.file-input-wrap')?.querySelector('.file-input-label');
  if (!label) return;
  const name = input.files[0]?.name;
  if (name) label.textContent = '📎 ' + name;
});

// ── Mini toast helper ─────────────────────────────────────────────────────────
function _showToast(message, type = 'info') {
  const toast = document.createElement('div');
  toast.className  = `flash-item ${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position:fixed; bottom:1.5rem; right:1.5rem; z-index:9999;
    animation: flashIn .3s ease;
  `;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = 'opacity .3s';
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 320);
  }, 2500);
}
