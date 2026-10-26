// Conjunto de ícones do portal. Grade 24x24, traço 1.75 (sobrescrito pela página/componente),
// pontas e junções arredondadas, cor = currentColor. Cada entrada traz o miolo do <svg>.

const C = '<circle cx="12" cy="12" r="9"/>';
const FILE =
  '<path d="M13.5 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5z"/>' +
  '<path d="M13.5 3v4a1.5 1.5 0 0 0 1.5 1.5h4"/>';
const CAL = '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>';
const CLIP =
  '<rect x="8.5" y="2.5" width="7" height="4" rx="1"/>' +
  '<path d="M15.5 4.5H17a2 2 0 0 1 2 2V19a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6.5a2 2 0 0 1 2-2h1.5"/>';
const CLOUD = '<path d="M7 18.5a4.5 4.5 0 0 1-.6-9A6 6 0 0 1 18 9.5a4.5 4.5 0 0 1-.5 9z"/>';
const SHIELD = '<path d="M12 3l7.5 3v5.5c0 4.6-3.2 8.2-7.5 9.5-4.3-1.3-7.5-4.9-7.5-9.5V6z"/>';
const AXES = '<path d="M3.5 3.5v15a2 2 0 0 0 2 2h15"/>';
const THUMB =
  '<path d="M7 10.5V20M7 10.5l3.8-7a2 2 0 0 1 3.7 1.3L13.8 9h4.7a2 2 0 0 1 2 2.3l-1.2 7a2 2 0 0 1-2 1.7H7"/>' +
  '<path d="M7 20H4.5a1 1 0 0 1-1-1v-7.5a1 1 0 0 1 1-1H7"/>';
const dot = (x, y) => `<path d="M${x} ${y}h.01"/>`;

const r = (n) => Math.round(n * 100) / 100;
const polar = (radius, deg) => {
  const a = (deg * Math.PI) / 180;
  return [r(12 + radius * Math.cos(a)), r(12 + radius * Math.sin(a))];
};

function gear() {
  const pts = [];
  for (let i = 0; i < 8; i++) {
    const a = i * 45;
    pts.push(polar(7.2, a - 17), polar(9.6, a - 9), polar(9.6, a + 9), polar(7.2, a + 17));
  }
  return `<path d="M${pts.map((p) => p.join(' ')).join('L')}z"/><circle cx="12" cy="12" r="3"/>`;
}

function rosette() {
  let d = '';
  for (let i = 0; i < 8; i++) {
    const [x, y] = polar(7.8, i * 45 - 67.5);
    const [cx, cy] = polar(10.6, i * 45 - 45);
    const [nx, ny] = polar(7.8, i * 45 - 22.5);
    d += (i === 0 ? `M${x} ${y}` : '') + `Q${cx} ${cy} ${nx} ${ny}`;
  }
  return `<path d="${d}z"/><path d="M8.6 12.2l2.3 2.3 4.5-4.7"/>`;
}

export const CATEGORIES = [
  'Navegação e setas',
  'Ações',
  'Status e feedback',
  'Arquivos e conteúdo',
  'Dados e sistema',
  'Pessoas e negócio',
  'Tempo e agenda',
];

// [nome, categoria, miolo do svg, nomes do Material Icons que ele substitui]
export const ICONS = [
  ['x', 0, '<path d="M6 6l12 12M18 6L6 18"/>', ['close']],
  ['menu', 0, '<path d="M4 6.5h16M4 12h16M4 17.5h16"/>', ['menu']],
  ['chevron-down', 0, '<path d="M6 9.5l6 6 6-6"/>', ['expand_more', 'keyboard_arrow_down']],
  ['chevron-up', 0, '<path d="M6 14.5l6-6 6 6"/>', ['expand_less', 'keyboard_arrow_up']],
  ['chevron-left', 0, '<path d="M14.5 6l-6 6 6 6"/>', ['chevron_left']],
  ['chevron-right', 0, '<path d="M9.5 6l6 6-6 6"/>', ['chevron_right']],
  ['chevrons-left', 0, '<path d="M12 6l-6 6 6 6M18 6l-6 6 6 6"/>', ['keyboard_double_arrow_left']],
  ['chevrons-right', 0, '<path d="M6 6l6 6-6 6M12 6l6 6-6 6"/>', ['keyboard_double_arrow_right']],
  ['chevrons-up-down', 0, '<path d="M8 9l4-4 4 4M8 15l4 4 4-4"/>', ['unfold_more']],
  ['chevrons-down-up', 0, '<path d="M8 5l4 4 4-4M8 19l4-4 4 4"/>', ['unfold_less']],
  ['caret-down', 0, '<path d="M7.5 10h9L12 15z" fill="currentColor"/>', ['arrow_drop_down']],
  ['arrow-left', 0, '<path d="M19 12H5M11 6l-6 6 6 6"/>', ['arrow_back']],
  ['arrow-right', 0, '<path d="M5 12h14M13 6l6 6-6 6"/>', ['arrow_forward', 'arrow_right_alt', 'east']],
  ['arrow-up', 0, '<path d="M12 19V5M6 11l6-6 6 6"/>', ['arrow_upward', 'north']],
  ['arrow-down', 0, '<path d="M12 5v14M6 13l6 6 6-6"/>', ['arrow_downward', 'south']],
  ['arrow-up-right', 0, '<path d="M7 17L17 7M9 7h8v8"/>', ['call_made']],
  ['arrow-down-left', 0, '<path d="M17 7L7 17M15 17H7V9"/>', ['call_received']],
  [
    'arrows-left-right',
    0,
    '<path d="M4 8.5h15M15.5 5L19 8.5 15.5 12M20 15.5H5M8.5 12L5 15.5 8.5 19"/>',
    ['swap_horiz', 'sync_alt'],
  ],
  [
    'arrows-up-down',
    0,
    '<path d="M8.5 20V5M5 8.5L8.5 5 12 8.5M15.5 4v15M12 15.5l3.5 3.5 3.5-3.5"/>',
    ['swap_vert'],
  ],
  [
    'split',
    0,
    '<path d="M12 21v-8M12 13L5.5 6.5M12 13l6.5-6.5M5.5 11.5v-5h5M18.5 11.5v-5h-5"/>',
    ['call_split', 'alt_route'],
  ],
  [
    'corner-down-right',
    0,
    '<path d="M5 4v7a3 3 0 0 0 3 3h11M15 10l4 4-4 4"/>',
    ['subdirectory_arrow_right'],
  ],
  [
    'external-link',
    0,
    '<path d="M13 5h6v6M19 5l-8 8M17 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2h4"/>',
    ['open_in_new'],
  ],
  [
    'log-in',
    0,
    '<path d="M10 8l4 4-4 4M14 12H3.5M14 4.5h4a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-4"/>',
    ['input'],
  ],
  [
    'log-out',
    0,
    '<path d="M9 4.5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h3M15 8l4 4-4 4M19 12H9"/>',
    ['logout', 'output'],
  ],
  [
    'grip-vertical',
    0,
    '<g fill="currentColor" stroke="none"><circle cx="9" cy="6" r="1.3"/><circle cx="15" cy="6" r="1.3"/><circle cx="9" cy="12" r="1.3"/><circle cx="15" cy="12" r="1.3"/><circle cx="9" cy="18" r="1.3"/><circle cx="15" cy="18" r="1.3"/></g>',
    ['drag_indicator'],
  ],
  [
    'pointer-click',
    0,
    '<path d="M9 9l4.5 11 1.6-4.4 4.4-1.6zM9 4.5V3M5.2 5.2L4.1 4.1M4.5 9H3M13.8 4.1l-1 1"/>',
    ['touch_app'],
  ],

  ['plus', 1, '<path d="M12 5v14M5 12h14"/>', ['add']],
  ['minus', 1, '<path d="M5 12h14"/>', ['remove']],
  ['plus-circle', 1, C + '<path d="M12 8v8M8 12h8"/>', ['add_circle']],
  ['check', 1, '<path d="M5 12.5l4.5 4.5L19 7.5"/>', ['check']],
  [
    'pencil',
    1,
    '<path d="M15.5 4.5l4 4L9 19l-5 1 1-5zM13.5 6.5l4 4"/>',
    ['edit', 'edit_square', 'drive_file_rename_outline'],
  ],
  [
    'note-pencil',
    1,
    '<path d="M4 6h10M4 10.5h7M4 15h4M18.5 9.5l2 2-6.5 6.5-2.8.6.6-2.8z"/>',
    ['edit_note'],
  ],
  [
    'trash',
    1,
    '<path d="M4 6.5h16M9.5 6.5v-2a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2M6 6.5l.9 12.6a2 2 0 0 0 2 1.9h6.2a2 2 0 0 0 2-1.9L18 6.5M10 11v5.5M14 11v5.5"/>',
    ['delete', 'delete_outline'],
  ],
  [
    'copy',
    1,
    '<rect x="8.5" y="8.5" width="12" height="12" rx="2"/><path d="M15.5 8.5v-3a2 2 0 0 0-2-2h-8a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h3"/>',
    ['content_copy'],
  ],
  [
    'save',
    1,
    '<path d="M5.5 3.5H16l4 4v11a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2z"/><path d="M8 3.5V8h7V3.5M7.5 20.5V14a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v6.5"/>',
    ['save'],
  ],
  ['send', 1, '<path d="M21 3L10.5 13.5M21 3l-6.5 18-4-7.5-7.5-4z"/>', ['send']],
  [
    'paperclip',
    1,
    '<path d="M20 11.5l-8.2 8.2a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.4 8.4a1.7 1.7 0 0 1-2.4-2.4l7.6-7.6"/>',
    ['attach_file'],
  ],
  [
    'download',
    1,
    '<path d="M12 4v11M7.5 10.5L12 15l4.5-4.5M4.5 16v2.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V16"/>',
    ['download', 'file_download'],
  ],
  ['cloud-upload', 1, CLOUD + '<path d="M12 17v-5.5M9.7 13.8L12 11.5l2.3 2.3"/>', ['cloud_upload']],
  ['search', 1, '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20"/>', ['search']],
  [
    'search-x',
    1,
    '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5L20 20M8.5 8.5l4 4M12.5 8.5l-4 4"/>',
    ['search_off'],
  ],
  ['filter', 1, '<path d="M4 5h16l-6.2 7.3V18l-3.6 2v-7.7z"/>', ['filter_alt']],
  [
    'filter-x',
    1,
    '<path d="M3.5 4.5h14l-5.3 6.3V17l-3.4 2.2v-8.4zM15.5 14.5l5 5M20.5 14.5l-5 5"/>',
    ['filter_alt_off', 'filter_list_off'],
  ],
  [
    'eye',
    1,
    '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    ['visibility'],
  ],
  [
    'refresh',
    1,
    '<path d="M20 11a8 8 0 0 0-14.3-4.3L4 9M4 4.5V9h4.5M4 13a8 8 0 0 0 14.3 4.3L20 15M20 19.5V15h-4.5"/>',
    ['refresh', 'sync', 'autorenew'],
  ],
  [
    'rotate-ccw',
    1,
    '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.5M3.5 3.5v5h5"/>',
    ['replay'],
  ],
  ['undo', 1, '<path d="M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>', ['undo']],
  ['settings', 1, gear(), ['settings']],
  [
    'sliders',
    1,
    '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    ['settings_suggest'],
  ],
  ['toggle-on', 1, '<rect x="2" y="6.5" width="20" height="11" rx="5.5"/><circle cx="16.5" cy="12" r="3" fill="currentColor"/>', ['toggle_on']],
  ['toggle-off', 1, '<rect x="2" y="6.5" width="20" height="11" rx="5.5"/><circle cx="7.5" cy="12" r="3"/>', ['toggle_off']],
  ['play-circle', 1, C + '<path d="M10 8.5v7l5.5-3.5z"/>', ['play_circle']],
  ['pause-circle', 1, C + '<path d="M10 9v6M14 9v6"/>', ['pause_circle']],

  ['check-circle', 2, C + '<path d="M8 12.5l2.75 2.75L16 10"/>', ['check_circle', 'task_alt']],
  ['x-circle', 2, C + '<path d="M9.5 9.5l5 5M14.5 9.5l-5 5"/>', ['cancel']],
  ['minus-circle', 2, C + '<path d="M8 12h8"/>', ['do_not_disturb_on']],
  ['circle', 2, '<circle cx="12" cy="12" r="8"/>', ['radio_button_unchecked']],
  ['alert-circle', 2, C + '<path d="M12 7.5V13"/>' + dot(12, 16.5), ['error', 'error_outline']],
  [
    'alert-triangle',
    2,
    '<path d="M10.3 4.3L2.9 17.5a2 2 0 0 0 1.7 3h14.8a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4"/>' +
      dot(12, 17),
    ['warning'],
  ],
  ['info', 2, C + '<path d="M12 11v5.5"/>' + dot(12, 7.75), ['info']],
  [
    'help-circle',
    2,
    C + '<path d="M9.5 9.3a2.6 2.6 0 0 1 5 .9c0 1.7-2.5 2.3-2.5 3.8"/>' + dot(12, 17),
    ['help_outline'],
  ],
  ['ban', 2, C + '<path d="M5.6 5.6l12.8 12.8"/>', ['block']],
  ['flag', 2, '<path d="M5 21V4.5M5 4.5c4.5-2.5 7 2.5 13 0v9c-6 2.5-8.5-2.5-13 0"/>', ['flag']],
  ['zap', 2, '<path d="M13 2.5L5 13.5h6l-1 8 8-11h-6z"/>', ['flash_on']],
  ['thumbs-up', 2, THUMB, ['thumb_up']],
  ['thumbs-down', 2, `<g transform="rotate(180 12 12)">${THUMB}</g>`, ['thumb_down']],
  ['badge-check', 2, rosette(), ['verified']],
  ['shield', 2, SHIELD, ['shield', 'security', 'admin_panel_settings']],
  ['shield-check', 2, SHIELD + '<path d="M9 12l2.2 2.2L15.5 10"/>', ['verified_user']],
  [
    'lock-open',
    2,
    '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5v-3a4 4 0 0 1 7.8-1.2M12 14.5v2"/>',
    ['lock_open'],
  ],
  [
    'link-off',
    2,
    '<path d="M9.5 7.5L11 6a4.2 4.2 0 0 1 6 6l-1.5 1.5M14.5 16.5L13 18a4.2 4.2 0 0 1-6-6l1.5-1.5M4 4l16 16"/>',
    ['link_off'],
  ],
  ['cloud-off', 2, CLOUD + '<path d="M3.5 3.5l17 17"/>', ['cloud_off']],
  [
    'square-1',
    2,
    '<rect x="3.5" y="3.5" width="17" height="17" rx="3"/><path d="M10 9.5l2.5-2v9"/>',
    ['looks_one'],
  ],
  [
    'square-2',
    2,
    '<rect x="3.5" y="3.5" width="17" height="17" rx="3"/><path d="M9.5 9.5a2.5 2.5 0 0 1 5 0c0 1.8-5 3.6-5 7h5"/>',
    ['looks_two'],
  ],
  [
    'hourglass',
    2,
    '<path d="M6.5 3.5h11M6.5 20.5h11M8 3.5v3.2a4 4 0 0 0 1.6 3.2L12 12l2.4-2.1A4 4 0 0 0 16 6.7V3.5M8 20.5v-3.2a4 4 0 0 1 1.6-3.2L12 12l2.4 2.1a4 4 0 0 1 1.6 3.2v3.2"/>',
    ['hourglass_empty', 'hourglass_top'],
  ],
  [
    'gauge',
    2,
    '<path d="M3.5 16a8.5 8.5 0 1 1 17 0M12 16l3.5-4.5"/><circle cx="12" cy="16" r="1.3"/>',
    ['network_check'],
  ],
  ['activity', 2, '<path d="M3 12h4l2.5-6 4 12 2.5-6h5"/>', ['monitor_heart']],

  ['file', 3, FILE, ['insert_drive_file']],
  [
    'file-text',
    3,
    FILE + '<path d="M8.5 12.5h7M8.5 16h7M8.5 9H11"/>',
    ['description', 'article', 'text_snippet', 'summarize'],
  ],
  ['file-plus', 3, FILE + '<path d="M12 11.5v6M9 14.5h6"/>', ['post_add']],
  ['file-upload', 3, FILE + '<path d="M12 18v-6M9.5 14.5L12 12l2.5 2.5"/>', ['upload_file']],
  [
    'file-zip',
    3,
    FILE + '<path d="M10 3v2M10 7v2M10 11v2"/><rect x="8.5" y="13.5" width="3" height="4" rx="1"/>',
    ['folder_zip'],
  ],
  [
    'file-pdf',
    3,
    FILE + '<path d="M8.5 17.5c1.8-1.2 3-3.5 3.5-6.5.5 3 2 5 4 5.5-2.5-.3-5.3.2-7.5 1z"/>',
    ['picture_as_pdf'],
  ],
  [
    'folder',
    3,
    '<path d="M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    ['folder'],
  ],
  [
    'folder-open',
    3,
    '<path d="M3 18V7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2v1M3 18l2.6-6.4A1.5 1.5 0 0 1 7 10.5h13.3a1 1 0 0 1 .9 1.4l-2.6 6.9a2 2 0 0 1-1.8 1.2H5a2 2 0 0 1-2-2z"/>',
    ['folder_open'],
  ],
  [
    'image',
    3,
    '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="9.5" r="1.8"/><path d="M3.5 18L9 12.5l3.5 3.5 2.5-2.5 5.5 5"/>',
    ['image', 'photo', 'gif'],
  ],
  [
    'video',
    3,
    '<rect x="2.5" y="6" width="13.5" height="12" rx="2"/><path d="M16 10.5l5.5-3v9l-5.5-3"/>',
    ['movie'],
  ],
  ['clipboard-list', 3, CLIP + '<path d="M9 11h6M9 14.5h6M9 18h3.5"/>', ['assignment']],
  ['clipboard-check', 3, CLIP + '<path d="M9 14l2 2 4-4.5"/>', ['fact_check']],
  ['clipboard-alert', 3, CLIP + '<path d="M12 10.5v4"/>' + dot(12, 17.5), ['assignment_late']],
  [
    'books',
    3,
    '<path d="M4 18.5v-13A1.5 1.5 0 0 1 5.5 4H9v16H5.5A1.5 1.5 0 0 1 4 18.5zM9 4h4v16H9M13.8 5.2l3.8-1 3.9 14.6-3.8 1z"/>',
    ['library_books'],
  ],
  [
    'inbox',
    3,
    '<path d="M3 13.5h5l1.5 2.5h5l1.5-2.5h5M5.5 5h13l2.5 8.5V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4.5z"/>',
    ['inbox'],
  ],
  [
    'archive-box',
    3,
    '<rect x="3" y="4" width="18" height="5" rx="1.5"/><path d="M4.5 9v9.5A1.5 1.5 0 0 0 6 20h12a1.5 1.5 0 0 0 1.5-1.5V9M10 13h4"/>',
    ['inventory_2'],
  ],
  [
    'message',
    3,
    '<path d="M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v10a1.5 1.5 0 0 1-1.5 1.5H9L4 21z"/>',
    ['chat'],
  ],
  [
    'mail-send',
    3,
    '<path d="M20 11V6.5A1.5 1.5 0 0 0 18.5 5h-13A1.5 1.5 0 0 0 4 6.5v10A1.5 1.5 0 0 0 5.5 18H12M4 6.5l8 5.5 8-5.5M16 19h5M19 17l2 2-2 2"/>',
    ['outgoing_mail'],
  ],

  [
    'table',
    4,
    '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9.5h18M3 14.8h18M9.5 9.5V20"/>',
    ['grid_on', 'table_chart', 'table_view'],
  ],
  [
    'rows',
    4,
    '<rect x="3.5" y="4" width="17" height="7" rx="1.5"/><rect x="3.5" y="13" width="17" height="7" rx="1.5"/>',
    ['view_agenda', 'table_rows'],
  ],
  [
    'list',
    4,
    '<path d="M9 6.5h11M9 12h11M9 17.5h11"/>' + dot(4.5, 6.5) + dot(4.5, 12) + dot(4.5, 17.5),
    ['list_alt', 'view_list'],
  ],
  ['list-check', 4, '<path d="M4 6.5h11M4 12h11M4 17.5h6M14 17l2.2 2.2L20.5 15"/>', ['playlist_add_check']],
  ['align-left', 4, '<path d="M4 7h16M4 12h16M4 17h10"/>', ['notes']],
  [
    'grid',
    4,
    '<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>',
    ['dataset'],
  ],
  [
    'layout-dashboard',
    4,
    '<rect x="3.5" y="3.5" width="7" height="9" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="5" rx="1.5"/><rect x="13.5" y="11.5" width="7" height="9" rx="1.5"/><rect x="3.5" y="15.5" width="7" height="5" rx="1.5"/>',
    ['dashboard'],
  ],
  [
    'database',
    4,
    '<ellipse cx="12" cy="6" rx="7.5" ry="2.8"/><path d="M4.5 6v12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8V6M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
    ['storage'],
  ],
  ['layers', 4, '<path d="M12 3.5l9 4.5-9 4.5-9-4.5zM3 12l9 4.5 9-4.5M3 16.5l9 4.5 9-4.5"/>', ['layers']],
  [
    'hierarchy',
    4,
    '<rect x="9" y="3" width="6" height="5" rx="1.2"/><rect x="3" y="16" width="6" height="5" rx="1.2"/><rect x="15" y="16" width="6" height="5" rx="1.2"/><path d="M12 8v4M6 16v-2.5A1.5 1.5 0 0 1 7.5 12h9a1.5 1.5 0 0 1 1.5 1.5V16"/>',
    ['account_tree'],
  ],
  ['line-chart', 4, AXES + '<path d="M7.5 15l4-4.5 3 3 5.5-6.5"/>', ['show_chart']],
  ['bar-chart', 4, AXES + '<path d="M8 16.5v-4M12.5 16.5V8M17 16.5v-6"/>', ['bar_chart', 'analytics']],
  [
    'chart-search',
    4,
    '<path d="M3.5 3.5v15a2 2 0 0 0 2 2h7M7.5 14l3.5-4 3 2.5 4-5"/><circle cx="17.5" cy="17" r="2.5"/><path d="M19.3 18.8l1.7 1.7"/>',
    ['query_stats'],
  ],
  ['code', 4, '<path d="M8.5 7l-5 5 5 5M15.5 7l5 5-5 5M13.5 4.5l-3 15"/>', ['code']],
  [
    'braces',
    4,
    '<path d="M8 4H7a2 2 0 0 0-2 2v3.5A2.5 2.5 0 0 1 3 12a2.5 2.5 0 0 1 2 2.5V18a2 2 0 0 0 2 2h1M16 4h1a2 2 0 0 1 2 2v3.5a2.5 2.5 0 0 0 2 2.5 2.5 2.5 0 0 0-2 2.5V18a2 2 0 0 1-2 2h-1"/>',
    ['data_object'],
  ],
  ['plug', 4, '<path d="M9 3.5v4M15 3.5v4M7 7.5h10v3a5 5 0 0 1-10 0zM12 15.5v5"/>', ['cable']],
  ['monitor', 4, '<rect x="2.5" y="4" width="19" height="12.5" rx="2"/><path d="M8 20.5h8M12 16.5v4"/>', ['desktop_windows']],
  [
    'sun',
    4,
    '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
    ['light_mode'],
  ],
  ['moon', 4, '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>', ['dark_mode']],
  [
    'bot',
    4,
    '<rect x="4.5" y="8" width="15" height="11" rx="3"/><circle cx="12" cy="4" r="1"/><path d="M12 5v3M9 12.5V14M15 12.5V14M2.5 12.5v3M21.5 12.5v3"/>',
    ['android'],
  ],
  [
    'wrench',
    4,
    '<path d="M15.5 3.5a5 5 0 0 0-4.6 6.9l-7 7a1.8 1.8 0 0 0 2.6 2.6l7-7A5 5 0 0 0 20.5 8.5l-3 3-2.6-.4-.4-2.6 3-3z"/>',
    ['precision_manufacturing'],
  ],
  [
    'flask',
    4,
    '<path d="M9.5 3.5h5M10 3.5v6l-5.2 8.8a1.5 1.5 0 0 0 1.3 2.2h11.8a1.5 1.5 0 0 0 1.3-2.2L14 9.5v-6M7.2 14.5h9.6"/>',
    ['science'],
  ],
  [
    'globe',
    4,
    C + '<path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
    ['language'],
  ],
  ['hash', 4, '<path d="M9.5 4L8 20M16 4l-1.5 16M4.5 9h15M4 15h15"/>', ['tag']],
  [
    'shapes',
    4,
    '<path d="M7.5 3.5l4 6.5h-8z"/><circle cx="17" cy="7" r="3.5"/><rect x="4" y="13.5" width="7" height="7" rx="1.5"/><path d="M17 13.5v7M13.5 17h7"/>',
    ['category'],
  ],

  ['user', 5, '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>', ['person']],
  [
    'user-circle',
    5,
    C + '<circle cx="12" cy="10" r="3"/><path d="M6.5 18.5a6.5 6.5 0 0 1 11 0"/>',
    ['account_circle'],
  ],
  [
    'users',
    5,
    '<circle cx="9" cy="8.5" r="3.5"/><path d="M3 19.5a6 6 0 0 1 12 0M15.5 5.2a3.5 3.5 0 0 1 0 6.6M17.5 14.2a6 6 0 0 1 3.5 5.3"/>',
    ['group'],
  ],
  [
    'users-group',
    5,
    '<circle cx="12" cy="8" r="3"/><circle cx="5" cy="10" r="2"/><circle cx="19" cy="10" r="2"/><path d="M6.5 19a5.5 5.5 0 0 1 11 0M2 18a3.5 3.5 0 0 1 3-3.4M22 18a3.5 3.5 0 0 0-3-3.4"/>',
    ['groups_3'],
  ],
  [
    'id-card',
    5,
    '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="8.5" cy="11" r="2"/><path d="M5.5 16a3 3 0 0 1 6 0M14 10h4M14 13.5h3"/>',
    ['badge'],
  ],
  [
    'building',
    5,
    '<path d="M4 20.5V5a1.5 1.5 0 0 1 1.5-1.5h7A1.5 1.5 0 0 1 14 5v15.5M14 9.5h4.5A1.5 1.5 0 0 1 20 11v9.5M2.5 20.5h19M7.5 7.5h3M7.5 11h3M7.5 14.5h3"/>' +
      dot(17, 14) +
      dot(17, 17),
    ['apartment'],
  ],
  [
    'landmark',
    5,
    '<path d="M3 9.5L12 4l9 5.5M4 9.5h16M5.5 9.5v8M10 9.5v8M14 9.5v8M18.5 9.5v8M3 20.5h18M4 17.5h16"/>',
    ['account_balance'],
  ],
  [
    'wallet',
    5,
    '<rect x="3" y="6" width="18" height="14" rx="2.5"/><path d="M6 6l9.5-2.8a1.2 1.2 0 0 1 1.5 1.1V6M21 11h-4a2 2 0 0 0 0 4h4"/>' +
      dot(17, 13),
    ['account_balance_wallet'],
  ],
  [
    'banknote',
    5,
    '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/>' + dot(5.5, 12) + dot(18.5, 12),
    ['payments'],
  ],
  ['credit-card', 5, '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M2.5 9.5h19M6 15h4"/>', ['payment']],
  [
    'pix',
    5,
    '<rect x="5.5" y="5.5" width="13" height="13" rx="3.5" transform="rotate(45 12 12)"/><path d="M8.5 12l2.1-2.1a2 2 0 0 1 2.8 0L15.5 12M8.5 12l2.1 2.1a2 2 0 0 0 2.8 0L15.5 12"/>',
    ['pix'],
  ],
  [
    'percent',
    5,
    '<path d="M19 5L5 19"/><circle cx="7" cy="7" r="2.5"/><circle cx="17" cy="17" r="2.5"/>',
    ['percent'],
  ],
  [
    'scale',
    5,
    '<path d="M12 3.5v17M7 20.5h10M4.5 7.5h15M4.5 7.5l-2.5 6a2.8 2.8 0 0 0 5 0zM19.5 7.5l-2.5 6a2.8 2.8 0 0 0 5 0z"/>',
    ['balance'],
  ],
  [
    'gavel',
    5,
    '<rect x="10" y="3" width="5" height="10" rx="1" transform="rotate(-45 12.5 8)"/><path d="M10.7 9.8L4 16.5M12 20.5h8.5M14 20.5v-1.5a1 1 0 0 1 1-1h2.5a1 1 0 0 1 1 1v1.5"/>',
    ['gavel'],
  ],
  [
    'handshake',
    5,
    '<path d="M2 8l3-1.2 4 1.2M22 8l-3-1.2-3.5.7-6.2 4.9a1.3 1.3 0 0 0 1.8 1.9l2.4-1.8 5.2 4.5M4.8 14.5l4.2 4a1.3 1.3 0 0 0 1.9 0 1.3 1.3 0 0 0 1.9.1 1.3 1.3 0 0 0 1.9-.2l2.8-2.4M2 8v6.5h2.8M22 8v7.5h-3.2"/>',
    ['handshake'],
  ],
  [
    'store',
    5,
    '<path d="M4 10.5V20h16v-9.5M3 9.5L4.5 4h15L21 9.5a2.6 2.6 0 0 1-4.5 1.6 2.6 2.6 0 0 1-4.5 0 2.6 2.6 0 0 1-4.5 0A2.6 2.6 0 0 1 3 9.5zM9.5 20v-5h5v5"/>',
    ['storefront'],
  ],
  [
    'briefcase',
    5,
    '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a1.5 1.5 0 0 1 1.5-1.5h3A1.5 1.5 0 0 1 15 5v2M3 12.5h18"/>',
    ['business_center'],
  ],
  [
    'factory',
    5,
    '<path d="M3 20.5V10l5 3v-3l5 3v-3l5 3V4.5h3v16zM7 17h2M12 17h2"/>',
    ['factory'],
  ],
  [
    'hard-hat',
    5,
    '<path d="M2.5 17h19v1.5a1.5 1.5 0 0 1-1.5 1.5H4a1.5 1.5 0 0 1-1.5-1.5zM5 17v-2a7 7 0 0 1 14 0v2M10.5 8.2V13M13.5 8.2V13"/>',
    ['engineering'],
  ],
  ['map-pin', 5, '<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.5"/>', ['location_on']],
  [
    'phone',
    5,
    '<path d="M8.4 3.5H5.5a2 2 0 0 0-2 2.2A16 16 0 0 0 18.3 20.5a2 2 0 0 0 2.2-2v-2.9a1.5 1.5 0 0 0-1.1-1.4l-3-.8a1.5 1.5 0 0 0-1.5.4l-1.4 1.4a12 12 0 0 1-5.3-5.3l1.4-1.4a1.5 1.5 0 0 0 .4-1.5l-.8-3a1.5 1.5 0 0 0-1.4-1.1z"/>',
    ['phone'],
  ],

  ['clock', 6, C + '<path d="M12 7v5l3.5 2"/>', ['schedule']],
  [
    'history',
    6,
    '<path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1L3.5 8.5M3.5 3.5v5h5M12 7.5V12l3 2"/>',
    ['history', 'update'],
  ],
  ['calendar', 6, CAL, ['calendar_today', 'event']],
  ['calendar-check', 6, CAL + '<path d="M9 15l2 2 4-4"/>', ['event_available']],
  ['calendar-x', 6, CAL + '<path d="M10 13.5l4 4M14 13.5l-4 4"/>', ['event_busy']],
  ['calendar-clock', 6, CAL + '<circle cx="12" cy="15.2" r="3.2"/><path d="M12 13.7v1.5l1 .8"/>', ['event_repeat']],
  [
    'calendar-pencil',
    6,
    '<path d="M20.5 11V7a2 2 0 0 0-2-2h-13a2 2 0 0 0-2 2v11.5a2 2 0 0 0 2 2H11M3.5 10h17M8 3v4M16 3v4M18.5 13.5l2 2-4.5 4.5-2.5.5.5-2.5z"/>',
    ['edit_calendar'],
  ],
];
