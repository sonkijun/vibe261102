const CATEGORY_LABEL = { python: 'Python', web: 'Web', ios: 'iOS' };

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const escapeHTML = (s = '') =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} 로드 실패 (${res.status})`);
  return res.json();
}

/* ---------- Profile ---------- */
function renderProfile(p) {
  $$('[data-bind="name"]').forEach((el) => (el.textContent = p.name));
  $('[data-bind="role"]').textContent = p.role;
  $('[data-bind="tagline"]').textContent = p.tagline;
  $('[data-bind="initial"]').textContent = p.name.charAt(0).toUpperCase();
  $('[data-bind="about"]').innerHTML = p.about.map((t) => `<p>${escapeHTML(t)}</p>`).join('');

  const email = $('#contact-email');
  email.textContent = p.email;
  email.href = `mailto:${p.email}`;

  $('#copy-email').addEventListener('click', async () => {
    const status = $('#copy-status');
    try {
      await navigator.clipboard.writeText(p.email);
      status.textContent = '✓ 이메일 주소가 복사되었습니다.';
    } catch {
      status.textContent = '복사에 실패했어요. 주소를 직접 선택해 주세요.';
    }
    setTimeout(() => (status.textContent = ''), 2500);
  });

  const socialNames = { github: 'GitHub', linkedin: 'LinkedIn' };
  $('#social').innerHTML = Object.entries(p.links || {})
    .filter(([, url]) => url)
    .map(([key, url]) => `<a class="btn btn-ghost btn-sm" href="${escapeHTML(url)}" target="_blank" rel="noopener">${socialNames[key] || key}</a>`)
    .join('');

  $('#timeline').innerHTML = (p.experience || [])
    .map(
      (e) => `<li>
        <span class="period">${escapeHTML(e.period)}</span>
        <h3>${escapeHTML(e.title)}</h3>
        <p>${escapeHTML(e.desc)}</p>
      </li>`
    )
    .join('');
}

/* ---------- Skills ---------- */
function renderSkills(skills) {
  $('#skills-grid').innerHTML = skills
    .map(
      (s) => `<article class="skill-card" data-cat="${s.id}">
        <div class="skill-icon" aria-hidden="true">${s.icon}</div>
        <h3>${escapeHTML(s.title)}</h3>
        <p>${escapeHTML(s.summary)}</p>
        <div class="meter" role="meter" aria-label="${escapeHTML(s.title)} 숙련도" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${s.level}">
          <span style="--level:${s.level}%"></span>
        </div>
        <ul class="tags">${s.tags.map((t) => `<li class="tag">${escapeHTML(t)}</li>`).join('')}</ul>
      </article>`
    )
    .join('');
}

/* ---------- Projects ---------- */
function renderProjects(projects, filter = 'all') {
  const list = filter === 'all' ? projects : projects.filter((p) => p.category === filter);
  $('#projects-grid').innerHTML = list
    .map(
      (p, i) => `<button class="project-card" data-cat="${p.category}" data-id="${p.id}" style="animation-delay:${i * 50}ms" aria-haspopup="dialog">
        <div class="project-thumb" aria-hidden="true">${p.emoji || '💡'}</div>
        <div class="project-info">
          <span class="project-cat">${CATEGORY_LABEL[p.category]}</span>
          <h3>${escapeHTML(p.title)}</h3>
          <p>${escapeHTML(p.summary)}</p>
          <ul class="tags">${p.stack.map((t) => `<li class="tag">${escapeHTML(t)}</li>`).join('')}</ul>
        </div>
      </button>`
    )
    .join('');
}

function setupFilters(projects) {
  $$('.filter').forEach((btn) =>
    btn.addEventListener('click', () => {
      $$('.filter').forEach((b) => {
        b.classList.toggle('is-active', b === btn);
        b.setAttribute('aria-selected', b === btn);
      });
      renderProjects(projects, btn.dataset.filter);
    })
  );
}

function setupModal(projects) {
  const modal = $('#project-modal');
  const linkLabels = { demo: '▶ 데모 보기', github: 'GitHub', appstore: ' App Store' };

  $('#projects-grid').addEventListener('click', (e) => {
    const card = e.target.closest('.project-card');
    if (!card) return;
    const p = projects.find((x) => x.id === card.dataset.id);

    const links = Object.entries(p.links || {}).filter(([, url]) => url);
    $('#modal-body').innerHTML = `
      <div class="project-thumb" data-cat="${p.category}" aria-hidden="true">${p.emoji || '💡'}</div>
      <div class="modal-content" data-cat="${p.category}">
        <span class="project-cat">${CATEGORY_LABEL[p.category]}</span>
        <h3 id="modal-title">${escapeHTML(p.title)}</h3>
        <p>${escapeHTML(p.description)}</p>
        <dl>
          <dt>역할</dt><dd>${escapeHTML(p.role)}</dd>
          <dt>기술</dt><dd><ul class="tags">${p.stack.map((t) => `<li class="tag">${escapeHTML(t)}</li>`).join('')}</ul></dd>
        </dl>
        <div class="modal-links">
          ${
            links.length
              ? links.map(([k, url]) => `<a class="btn btn-primary btn-sm" href="${escapeHTML(url)}" target="_blank" rel="noopener">${linkLabels[k] || k}</a>`).join('')
              : '<span class="muted">데모·코드 링크 준비 중입니다.</span>'
          }
        </div>
      </div>`;
    modal.showModal();
  });

  $('.modal-close', modal).addEventListener('click', () => modal.close());
  // 바깥(backdrop) 클릭 시 닫기
  modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.close();
  });
}

/* ---------- UI: theme, nav, reveal ---------- */
function setupTheme() {
  $('.theme-toggle').addEventListener('click', () => {
    const root = document.documentElement;
    const current = root.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = current === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    try {
      localStorage.setItem('theme', next);
    } catch {}
  });
}

function setupNav() {
  const toggle = $('.nav-toggle');
  const menu = $('#nav-menu');
  const setOpen = (open) => {
    menu.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', open);
  };
  toggle.addEventListener('click', () => setOpen(!menu.classList.contains('is-open')));
  $$('a', menu).forEach((a) => a.addEventListener('click', () => setOpen(false)));

  // 현재 보고 있는 섹션 메뉴 강조
  const links = $$('a[href^="#"]', menu);
  const spy = new IntersectionObserver(
    (entries) =>
      entries.forEach((en) => {
        if (!en.isIntersecting) return;
        links.forEach((l) => l.classList.toggle('is-current', l.getAttribute('href') === `#${en.target.id}`));
      }),
    { rootMargin: '-45% 0px -50% 0px' }
  );
  $$('main section[id]').forEach((s) => spy.observe(s));
}

function setupReveal() {
  const io = new IntersectionObserver(
    (entries) =>
      entries.forEach((en) => {
        if (en.isIntersecting) {
          en.target.classList.add('is-visible');
          io.unobserve(en.target);
        }
      }),
    { threshold: 0.12 }
  );
  $$('.reveal').forEach((el) => io.observe(el));
}

/* ---------- Init ---------- */
async function init() {
  $('#year').textContent = new Date().getFullYear();
  setupTheme();
  setupNav();
  setupReveal();

  try {
    const [profile, skills, projects] = await Promise.all([
      loadJSON('data/profile.json'),
      loadJSON('data/skills.json'),
      loadJSON('data/projects.json'),
    ]);
    renderProfile(profile);
    renderSkills(skills);
    renderProjects(projects);
    setupFilters(projects);
    setupModal(projects);
  } catch (err) {
    console.error(err);
    $('#projects-grid').innerHTML =
      '<p>데이터를 불러오지 못했습니다. 로컬 서버(<code>python3 -m http.server</code>)로 실행해 주세요.</p>';
  }
}

init();
