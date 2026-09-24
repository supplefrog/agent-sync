'use strict';
// Local-only progressive enhancement: images remain embedded in the document.
const dialog = document.querySelector('#figure-dialog');
const title = document.querySelector('#figure-title');
const view = document.querySelector('.image-view');
const sizeButton = document.querySelector('#figure-size');
let opener;
for (const button of document.querySelectorAll('button.zoom')) {
  button.addEventListener('click', () => {
    opener = button;
    const source = button.querySelector('img');
    const image = document.createElement('img');
    image.src = source.src;
    image.alt = source.alt;
    image.style.setProperty('--native-width', `${Number(source.getAttribute('width')) || source.naturalWidth}px`);
    view.replaceChildren(image);
    view.classList.remove('actual');
    view.scrollTo(0, 0);
    sizeButton.setAttribute('aria-pressed', 'false');
    sizeButton.textContent = 'Actual size';
    title.textContent = source.alt.split('. Source:')[0];
    dialog.showModal();
  });
}
sizeButton.addEventListener('click', () => {
  const actual = view.classList.toggle('actual');
  sizeButton.setAttribute('aria-pressed', String(actual));
  sizeButton.textContent = actual ? 'Fit image' : 'Actual size';
});
document.querySelector('#figure-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => {
  const r = dialog.getBoundingClientRect();
  if (event.target === dialog && (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)) dialog.close();
});
dialog.addEventListener('close', () => {
  view.replaceChildren();
  opener?.focus({preventScroll:true});
});
for (const anchor of document.querySelectorAll('.contents a')) {
  anchor.addEventListener('click', () => {
    anchor.closest('details').open = false;
    requestAnimationFrame(() => {
      const target = document.getElementById(anchor.getAttribute('href').slice(1));
      target?.scrollIntoView();
      target?.focus({preventScroll:true});
    });
  });
}
