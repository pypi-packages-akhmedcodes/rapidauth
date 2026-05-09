/* ============================================================
   RapidAuth Docs — docs.js
   Sidebar navigation, scroll tracking, search, copy, mobile
   ============================================================ */

(function () {
  'use strict';

  /* ── Sidebar active tracking ─────────────────────────────── */
  const sections = [];
  let ticking = false;

  function collectSections() {
    document.querySelectorAll('.doc-section[id]').forEach(s => {
      sections.push({ id: s.id, el: s });
    });
  }

  function getActiveId() {
    const offset = 80;
    let active = sections[0]?.id;
    for (const s of sections) {
      const rect = s.el.getBoundingClientRect();
      if (rect.top - offset <= 0) active = s.id;
      else break;
    }
    return active;
  }

  function updateActiveLink(id) {
    document.querySelectorAll('.sidebar-link').forEach(a => {
      const isActive = a.getAttribute('href') === '#' + id;
      a.classList.toggle('active', isActive);
      if (isActive) {
        const group = a.closest('.sidebar-group');
        if (group && group.classList.contains('collapsed')) {
          group.classList.remove('collapsed');
        }
      }
    });
  }

  window.addEventListener('scroll', () => {
    if (!ticking) {
      requestAnimationFrame(() => {
        updateActiveLink(getActiveId());
        ticking = false;
      });
      ticking = true;
    }
  }, { passive: true });

  /* ── Smooth scroll to section ────────────────────────────── */
  document.addEventListener('click', e => {
    const link = e.target.closest('.sidebar-link');
    if (!link) return;
    const href = link.getAttribute('href');
    if (!href || !href.startsWith('#')) return;
    e.preventDefault();
    const target = document.querySelector(href);
    if (target) {
      const y = target.getBoundingClientRect().top + window.scrollY - 72;
      window.scrollTo({ top: y, behavior: 'smooth' });
      history.pushState(null, '', href);
    }
    /* Close mobile sidebar */
    document.getElementById('sidebar')?.classList.remove('open');
    document.getElementById('overlay')?.classList.remove('show');
  });

  /* ── Collapsible sidebar groups ──────────────────────────── */
  document.addEventListener('click', e => {
    const toggle = e.target.closest('.group-toggle');
    if (!toggle) return;
    const group = toggle.closest('.sidebar-group');
    if (group) group.classList.toggle('collapsed');
  });

  /* ── Copy buttons ────────────────────────────────────────── */
  document.addEventListener('click', e => {
    const btn = e.target.closest('.copy-btn');
    if (!btn) return;
    const block = btn.closest('.code-block');
    if (!block) return;
    const code = block.querySelector('code');
    if (!code) return;
    navigator.clipboard.writeText(code.innerText.trim()).then(() => {
      btn.textContent = 'copied!';
      btn.classList.add('copied');
      setTimeout(() => { btn.textContent = 'copy'; btn.classList.remove('copied'); }, 1800);
    });
  });

  /* ── Mobile sidebar toggle ────────────────────────────────── */
  const menuBtn  = document.getElementById('menu-toggle');
  const sidebar  = document.getElementById('sidebar');
  const overlay  = document.getElementById('overlay');

  menuBtn?.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('show');
  });
  overlay?.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('show');
  });

  /* ── Search ─────────────────────────────────────────────── */
  const searchInput = document.getElementById('doc-search');
  const sidebarLinks = () => document.querySelectorAll('.sidebar-link');

  searchInput?.addEventListener('input', () => {
    const q = searchInput.value.toLowerCase().trim();
    if (!q) {
      sidebarLinks().forEach(a => {
        a.closest('li').style.display = '';
      });
      document.querySelectorAll('.sidebar-group').forEach(g => {
        g.style.display = '';
      });
      return;
    }
    document.querySelectorAll('.sidebar-group').forEach(group => {
      let anyVisible = false;
      group.querySelectorAll('.sidebar-link').forEach(a => {
        const text = a.textContent.toLowerCase();
        const show = text.includes(q);
        a.closest('li').style.display = show ? '' : 'none';
        if (show) anyVisible = true;
      });
      group.style.display = anyVisible ? '' : 'none';
      if (anyVisible) group.classList.remove('collapsed');
    });
  });

  /* ── Highlight.js ────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', () => {
    if (window.hljs) hljs.highlightAll();
    collectSections();
    updateActiveLink(getActiveId());

    /* Highlight active on load from hash */
    if (location.hash) {
      const id = location.hash.slice(1);
      setTimeout(() => {
        const target = document.getElementById(id);
        if (target) {
          const y = target.getBoundingClientRect().top + window.scrollY - 72;
          window.scrollTo({ top: y, behavior: 'smooth' });
        }
        updateActiveLink(id);
      }, 100);
    }
  });

  /* ── Nav scroll shadow ────────────────────────────────────── */
  window.addEventListener('scroll', () => {
    document.getElementById('nav')?.classList.toggle('scrolled', scrollY > 20);
  }, { passive: true });

})();
