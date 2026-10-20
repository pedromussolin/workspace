// Write rules of the fake BFF (task 25, part 1). Everything works on the `{ "api/path": response }`
// map that smoke.mjs serves from FIXTURES; the rules are pure functions that return a new map and
// never touch the one they received. Only createDataStore reads and writes files.
import fs from 'node:fs';
import path from 'node:path';

const AC = 'access-control';
const PEOPLE_KEY = `${AC}/people`;
const GROUPS_KEY = `${AC}/groups`;
const ROLES_KEY = `${AC}/roles`;
const PREVIEW_KEY = `${AC}/batch/preview`;
const APPLY_KEY = `${AC}/batch/apply`;
const personKey = (id) => `${AC}/people/${id}`;
const groupKey = (id) => `${AC}/groups/${id}`;
const holdersKey = (role) => `${AC}/roles/${role}/holders`;

/** The value the BFF `OrgType` gives to the internal organization, the only one that has no client. */
export const INTERNAL_ORGANIZATION = 'plgn';

// These POSTs only search: their body is a query, and appending it to the list would pollute (and
// save) the data on every typing in a search field.
const SEARCH_POSTS = new Set(['pre-trade/investor-vehicles', 'pre-trade/assets']);

export const noEffectWarning = (method, key) => `escrita sem efeito: ${method} ${key}`;

const isRecord = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const sameText = (a, b) => String(a ?? '').trim().toLowerCase() === String(b ?? '').trim().toLowerCase();
const slug = (text) => String(text).normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
const byText = (a, b) => (a < b ? -1 : a > b ? 1 : 0);

function uniqueId(base, used) {
  let id = base;
  for (let n = 2; used.includes(id); n += 1) id = `${base}-${n}`;
  return id;
}

/** Why a person has the state they have: the same rule of the BFF, so the list, the filter and the modal agree. */
export function scopeState({ organization, clientId }, clients) {
  if (!organization) return 'no-organization';
  if (organization === INTERNAL_ORGANIZATION) return 'ok';
  if (clientId == null) return 'no-client';
  // Without the client list (product-manager down in the real BFF) the number counts as valid.
  return clients === null || clients.some((client) => client.id === clientId) ? 'ok' : 'invalid-client';
}

export function hasAccessControl(data) {
  return [PEOPLE_KEY, GROUPS_KEY, ROLES_KEY].some((key) => isRecord(data[key]));
}

function readModel(data) {
  const people = (data[PEOPLE_KEY]?.people ?? []).map((person) => ({ ...person }));
  const groups = (data[GROUPS_KEY]?.groups ?? []).map((group) => {
    const detail = data[groupKey(group.id)];
    return {
      ...group,
      roles: [...(detail?.group?.roles ?? group.roles ?? [])],
      members: (detail?.members ?? []).map((member) => ({ ...member })),
    };
  });
  const direct = people.flatMap((person) =>
    (data[personKey(person.id)]?.roles ?? [])
      .filter((role) => role.via === 'direct')
      .map((role) => ({ personId: person.id, role: role.value, assignmentId: role.assignmentId ?? `a-${person.id}-${role.value}` }))
  );
  return {
    people,
    groups,
    direct,
    roles: (data[ROLES_KEY]?.roles ?? []).map((role) => ({ ...role })),
    organizations: data[`${AC}/settings`]?.organizations ?? [],
    clients: data[`${AC}/clients`]?.clients ?? null,
  };
}

const isMember = (group, personId) => group.members.some((member) => member.id === personId);
const identityOf = ({ id, displayName, mail, userPrincipalName }) => ({ id, displayName, mail, userPrincipalName });

function assignmentsOf(model, personId) {
  const own = model.direct
    .filter((assignment) => assignment.personId === personId)
    .map((assignment) => ({ value: assignment.role, via: 'direct', groupId: null, groupName: null, assignmentId: assignment.assignmentId }));
  const inherited = model.groups
    .filter((group) => isMember(group, personId))
    .flatMap((group) => group.roles.map((role) => ({ value: role, via: 'group', groupId: group.id, groupName: group.displayName, assignmentId: `a-${group.id}-${role}` })));
  return [...own, ...inherited].sort((a, b) => byText(a.value, b.value) || (a.via === b.via ? 0 : a.via === 'direct' ? -1 : 1));
}

function holdersOf(model, role) {
  const people = model.people.flatMap((person) => {
    const origins = assignmentsOf(model, person.id)
      .filter((assignment) => assignment.value === role)
      .map(({ via, groupId, groupName, assignmentId }) => ({ via, groupId, groupName, assignmentId }));
    return origins.length ? [{ id: person.id, displayName: person.displayName, mail: person.mail, origins }] : [];
  });
  const groups = model.groups
    .filter((group) => group.roles.includes(role))
    .map((group) => ({ id: group.id, displayName: group.displayName, memberCount: group.members.length, assignmentId: `a-${group.id}-${role}` }));
  return { people, groups };
}

// The primary facts are the direct assignments (in the person detail), the members and the roles of
// each group. Everything else (counters, inherited roles, holders) is derived here, so a change in
// one place can never leave the others behind.
function writeModel(data, model) {
  const next = { ...data };
  const roleCountOf = (personId) => new Set(assignmentsOf(model, personId).map((assignment) => assignment.value)).size;

  next[PEOPLE_KEY] = {
    ...data[PEOPLE_KEY],
    people: model.people.map((person) => ({
      ...person,
      roleCount: roleCountOf(person.id),
      groupCount: model.groups.filter((group) => isMember(group, person.id)).length,
    })),
  };
  for (const person of model.people) {
    const old = data[personKey(person.id)];
    next[personKey(person.id)] = {
      ...old,
      person: { ...old?.person, ...identityOf(person) },
      roles: assignmentsOf(model, person.id),
      groups: model.groups
        .filter((group) => isMember(group, person.id))
        .map((group) => ({ id: group.id, displayName: group.displayName, roleCount: group.roles.length, ownedByApp: group.ownedByApp })),
      scope:
        person.scopeState == null
          ? old?.scope ?? null
          : { organization: person.organization ?? null, clientId: person.clientId ?? null, clientName: person.clientName ?? null, state: person.scopeState },
    };
  }

  const groups = model.groups.map(({ members, ...group }) => ({ ...group, memberCount: members.length }));
  next[GROUPS_KEY] = { ...data[GROUPS_KEY], groups };
  for (const group of model.groups) {
    next[groupKey(group.id)] = { ...data[groupKey(group.id)], group: groups.find((entry) => entry.id === group.id), members: group.members };
  }

  const roles = model.roles.map((role) => {
    const holders = holdersOf(model, role.value);
    next[holdersKey(role.value)] = holders;
    return {
      ...role,
      userCount: holders.people.filter((person) => person.origins.some((origin) => origin.via === 'direct')).length,
      groupCount: holders.groups.length,
      peopleCount: holders.people.length,
    };
  });
  next[ROLES_KEY] = { ...data[ROLES_KEY], roles };

  const groupIds = new Set(model.groups.map((group) => group.id));
  const roleValues = new Set(model.roles.map((role) => role.value));
  for (const key of Object.keys(next)) {
    const group = key.match(/^access-control\/groups\/(.+)$/);
    const holders = key.match(/^access-control\/roles\/(.+)\/holders$/);
    if ((group && !groupIds.has(group[1])) || (holders && !roleValues.has(holders[1]))) delete next[key];
  }
  return next;
}

/** Rebuilds every derived value of the access control keys from the primary ones. */
export const syncAccessControl = (data) => writeModel(data, readModel(data));

const planned = (action) => (label, reason = null) => ({ action, label, reason });
const create = planned('create');
const assign = planned('assign');
const add = planned('add');
const update = planned('update');
const remove = planned('remove');
const del = planned('delete');
const skip = planned('skip');
const blocked = planned('blocked');

function lookupPerson(model, ref) {
  const entity = ref?.id
    ? model.people.find((person) => person.id === ref.id)
    : ref?.email
      ? model.people.find((person) => sameText(person.mail, ref.email) || sameText(person.userPrincipalName, ref.email))
      : undefined;
  return {
    entity,
    name: entity?.displayName ?? ref?.email ?? ref?.id ?? 'pessoa sem identificação',
    reason: ref?.id ? 'Pessoa não encontrada.' : 'E-mail não encontrado no diretório.',
  };
}

function lookupGroup(model, ref) {
  const entity = ref?.id
    ? model.groups.find((group) => group.id === ref.id)
    : ref?.name
      ? model.groups.find((group) => sameText(group.displayName, ref.name))
      : undefined;
  return { entity, name: entity?.displayName ?? ref?.name ?? ref?.id ?? 'grupo sem identificação', reason: 'Grupo não encontrado.' };
}

function roleIssue(model, value) {
  const role = model.roles.find((entry) => entry.value === value);
  if (!role) return 'Permissão não encontrada.';
  return role.inAzure ? null : 'A permissão ainda não existe no Azure.';
}

const hasRole = (model, role, isGroup, entity) =>
  isGroup ? entity.roles.includes(role) : model.direct.some((assignment) => assignment.personId === entity.id && assignment.role === role);

function giveRole(model, role, isGroup, entity, label) {
  if (hasRole(model, role, isGroup, entity)) return skip(label, 'Já tem.');
  if (isGroup) entity.roles.push(role);
  else model.direct.push({ personId: entity.id, role, assignmentId: `a-${entity.id}-${role}` });
  return assign(label);
}

function targetOf(model, principal) {
  const isGroup = principal?.kind === 'group';
  return { isGroup, ...(isGroup ? lookupGroup(model, principal) : lookupPerson(model, principal)) };
}

const OPERATIONS = {
  create_role(model, { value, displayName, description }) {
    const label = `Criar a permissão ${value}`;
    const existing = model.roles.find((role) => role.value === value);
    if (existing?.inAzure) return [skip(label, 'Já existe no Azure.')];
    if (existing) {
      existing.inAzure = true;
      existing.appRoleId ??= `r-${slug(value)}`;
      return [create(label)];
    }
    model.roles.push({
      value,
      displayName: displayName || value,
      description: description ?? '',
      appRoleId: `r-${slug(value)}`,
      isEnabled: true,
      inAzure: true,
      usedInCode: false,
      codeRefs: [],
      userCount: 0,
      groupCount: 0,
      deletable: true,
      notDeletableReason: null,
      permission: null,
      peopleCount: 0,
    });
    model.roles.sort((a, b) => byText(a.value, b.value));
    return [create(label)];
  },

  create_group(model, { displayName, description }) {
    const label = `Criar o grupo ${displayName}`;
    if (model.groups.some((group) => sameText(group.displayName, displayName))) return [skip(label, 'Já existe um grupo com esse nome.')];
    model.groups.push({
      id: uniqueId(`g-${slug(displayName)}`, model.groups.map((group) => group.id)),
      displayName,
      description: description || null,
      memberCount: 0,
      roles: [],
      ownedByApp: true,
      deletable: true,
      notDeletableReason: null,
      members: [],
    });
    return [create(label)];
  },

  assign_role(model, { role, principal }) {
    const target = targetOf(model, principal);
    const label = `Atribuir ${role} para ${target.isGroup ? 'o grupo ' : ''}${target.name}`;
    if (!target.entity) return [blocked(label, target.reason)];
    const issue = roleIssue(model, role);
    return [issue ? blocked(label, issue) : giveRole(model, role, target.isGroup, target.entity, label)];
  },

  remove_assignment(model, { role, principal }) {
    const target = targetOf(model, principal);
    const label = `Remover ${role} ${target.isGroup ? 'do grupo' : 'de'} ${target.name}`;
    if (!target.entity) return [blocked(label, target.reason)];
    if (!hasRole(model, role, target.isGroup, target.entity)) return [skip(label, 'Não tem.')];
    if (target.isGroup) target.entity.roles = target.entity.roles.filter((value) => value !== role);
    else model.direct = model.direct.filter((assignment) => !(assignment.personId === target.entity.id && assignment.role === role));
    return [remove(label)];
  },

  add_member(model, { group: groupRef, user }) {
    const group = lookupGroup(model, groupRef);
    const person = lookupPerson(model, user);
    const label = `Adicionar ${person.name} ao grupo ${group.name}`;
    if (!group.entity) return [blocked(label, group.reason)];
    if (!person.entity) return [blocked(label, person.reason)];
    if (isMember(group.entity, person.entity.id)) return [skip(label, 'Já é membro.')];
    group.entity.members.push(identityOf(person.entity));
    return [add(label)];
  },

  remove_member(model, { groupId, userId }) {
    const group = lookupGroup(model, { id: groupId });
    const member = group.entity?.members.find((entry) => entry.id === userId);
    const name = member?.displayName ?? model.people.find((person) => person.id === userId)?.displayName ?? userId;
    const label = `Tirar ${name} do grupo ${group.name}`;
    if (!group.entity) return [blocked(label, group.reason)];
    if (!member) return [skip(label, 'Não é membro.')];
    group.entity.members = group.entity.members.filter((entry) => entry.id !== userId);
    return [remove(label)];
  },

  delete_role(model, { value }) {
    const label = `Apagar a permissão ${value}`;
    if (!model.roles.some((role) => role.value === value)) return [blocked(label, 'Permissão não encontrada.')];
    model.roles = model.roles.filter((role) => role.value !== value);
    model.direct = model.direct.filter((assignment) => assignment.role !== value);
    for (const group of model.groups) group.roles = group.roles.filter((role) => role !== value);
    return [del(label)];
  },

  delete_group(model, { groupId }) {
    const group = lookupGroup(model, { id: groupId });
    const label = `Apagar o grupo ${group.name}`;
    if (!group.entity) return [blocked(label, group.reason)];
    model.groups = model.groups.filter((entry) => entry.id !== groupId);
    return [del(label)];
  },

  copy_assignments(model, { from, to }) {
    const label = `Atribuir ${to} a quem tem ${from}`;
    const toIssue = roleIssue(model, to);
    if (toIssue) return [blocked(label, toIssue)];
    if (roleIssue(model, from)) return [skip(label, `A permissão ${from} não existe no Azure: não há de quem copiar.`)];
    const owners = [
      ...model.people.filter((person) => hasRole(model, from, false, person)).map((entity) => ({ entity, isGroup: false })),
      ...model.groups.filter((group) => group.roles.includes(from)).map((entity) => ({ entity, isGroup: true })),
    ];
    if (!owners.length) return [skip(label, `Ninguém tem a permissão ${from}.`)];
    return owners.map(({ entity, isGroup }) =>
      giveRole(model, to, isGroup, entity, `Atribuir ${to} para ${isGroup ? 'o grupo ' : ''}${entity.displayName}, que tem ${from}`)
    );
  },

  set_person_scope(model, { user, organization, clientId }) {
    const person = lookupPerson(model, user);
    const org = organization || null;
    const parsed = Number(clientId);
    const client = org === INTERNAL_ORGANIZATION || clientId == null || !Number.isFinite(parsed) ? null : parsed;
    const clientName = client === null ? null : (model.clients?.find((entry) => entry.id === client)?.name ?? null);
    const orgName = model.organizations.find((option) => option.value === org)?.label ?? org ?? 'sem organização';
    const label = `Mudar ${person.name} para a organização ${orgName}${client === null ? ', sem cliente' : ` e o cliente ${clientName ?? client}`}`;
    if (!person.entity) return [blocked(label, person.reason)];
    if ((person.entity.organization ?? null) === org && (person.entity.clientId ?? null) === client) {
      return [skip(label, 'Já está com essa organização e esse cliente.')];
    }
    Object.assign(person.entity, { organization: org, clientId: client, clientName, scopeState: scopeState({ organization: org, clientId: client }, model.clients) });
    return [update(label)];
  },
};

// The preview and the apply run the same rules on a copy, one operation after the other, so what
// an operation creates (a role, a group) is there for the next ones, as in the real BFF.
function runOperations(data, operations) {
  const model = readModel(data);
  const items = operations.flatMap((operation, index) => {
    const handler = OPERATIONS[operation?.type];
    const results = handler ? handler(model, operation) : [blocked(`Operação ${operation?.type ?? 'sem tipo'}`, 'Operação desconhecida.')];
    return results.map(({ label, action, reason }) => ({ index, type: operation?.type ?? null, label, action, reason }));
  });
  return { model, items };
}

const countBy = (items, field) => items.reduce((total, item) => ({ ...total, [item[field]]: (total[item[field]] ?? 0) + 1 }), {});
const STATUS = { skip: 'skipped', blocked: 'failed' };

export function previewBatch(data, operations) {
  const { items } = runOperations(data, operations);
  return { items, summary: countBy(items, 'action') };
}

/** `data` comes back only when something changed. */
export function applyBatch(data, operations) {
  const { model, items } = runOperations(data, operations);
  const results = items.map((item) => ({ ...item, status: STATUS[item.action] ?? 'ok', error: item.action === 'blocked' ? item.reason : null }));
  const changed = results.some((item) => item.status === 'ok');
  return { items: results, summary: countBy(results, 'status'), data: changed ? writeModel(data, model) : undefined };
}

const LIST_FIELDS = ['records', 'items'];

function readList(value) {
  if (Array.isArray(value)) return value.every(isRecord) ? { items: value, field: null } : null;
  const field = LIST_FIELDS.find((name) => Array.isArray(value?.[name]));
  return field && value[field].every(isRecord) ? { items: value[field], field } : null;
}

// The counters follow by how much the list grew, not by its length: a page of the data may be
// only part of what `total` counts.
function withItems(value, list, items) {
  if (list.field === null) return items;
  const delta = items.length - list.items.length;
  const next = { ...value, [list.field]: items };
  if (typeof value.total === 'number') next.total = value.total + delta;
  if (typeof value.pagination?.total_count === 'number') next.pagination = { ...value.pagination, total_count: value.pagination.total_count + delta };
  return next;
}

const idField = (items) => (items.some((item) => 'id' in item) || !items.some((item) => 'key' in item) ? 'id' : 'key');
const idsOf = (item) => ['id', 'key'].filter((field) => item[field] != null).map((field) => [field, item[field]]);
const findItem = (items, id) => items.findIndex((item) => idsOf(item).some(([, value]) => String(value) === id));

function nextId(items, field) {
  const ids = items.map((item) => item[field]).filter((value) => value != null);
  if (ids.length && ids.every((value) => typeof value === 'number')) return Math.max(...ids) + 1;
  const parts = ids.map((value) => String(value).match(/^(.*?)(\d+)$/));
  if (parts.length && parts.every(Boolean) && new Set(parts.map((part) => part[1])).size === 1) {
    const max = Math.max(...parts.map((part) => Number(part[2])));
    return parts[0][1] + String(max + 1).padStart(parts[0][2].length, '0');
  }
  return uniqueId(`novo-${items.length + 1}`, ids.map(String));
}

function applyListWrite(data, method, key, body) {
  if (method === 'POST') {
    const list = readList(data[key]);
    if (SEARCH_POSTS.has(key) || !isRecord(body) || !list) return null;
    const field = idField(list.items);
    const item = { ...body, [field]: nextId(list.items, field) };
    return { status: 201, body: item, data: { ...data, [key]: withItems(data[key], list, [...list.items, item]) } };
  }

  const slash = key.lastIndexOf('/');
  if (slash < 0 || !['PUT', 'PATCH', 'DELETE'].includes(method)) return null;
  const listKey = key.slice(0, slash);
  const id = key.slice(slash + 1);
  const list = readList(data[listKey]);
  const index = list ? findItem(list.items, id) : -1;
  const detail = isRecord(data[key]);
  const next = { ...data };
  if (method === 'DELETE') {
    if (index < 0 && !(key in data)) return null;
    const removed = index >= 0 ? list.items[index] : data[key];
    if (index >= 0) next[listKey] = withItems(data[listKey], list, list.items.filter((_, position) => position !== index));
    delete next[key];
    return { status: 200, body: removed, data: next };
  }

  if (!isRecord(body) || (index < 0 && !detail)) return null;
  const merge = (current) => ({ ...current, ...body, ...Object.fromEntries(idsOf(current)) });
  let result = null;
  if (index >= 0) {
    result = merge(list.items[index]);
    next[listKey] = withItems(data[listKey], list, list.items.map((item, position) => (position === index ? result : item)));
  }
  if (detail) {
    result = merge(data[key]);
    next[key] = result;
  }
  return { status: 200, body: result, data: next };
}

/**
 * The fake BFF's answer to a write, or `null` when no rule covers it (the caller answers as for a
 * read and warns). `data` is set only when the write changed something.
 */
export function applyWrite(data, method, key, body) {
  if (key.startsWith(`${AC}/`)) {
    if (method !== 'POST' || !hasAccessControl(data) || (key !== PREVIEW_KEY && key !== APPLY_KEY)) return null;
    if (!Array.isArray(body?.operations)) return { status: 400, body: { detail: 'Informe a lista de operações.' } };
    if (key === PREVIEW_KEY) return { status: 200, body: previewBatch(data, body.operations) };
    const { data: next, ...response } = applyBatch(data, body.operations);
    return { status: 200, body: response, data: next };
  }
  return applyListWrite(data, method, key, body);
}

/**
 * The data the fake BFF serves. With `persist` (the portal in SERVE mode) every change goes to a
 * copy in `alteracoes/` next to the original, and the copy wins over the original from then on;
 * without it (the smoke) changes stay in memory and the disk is never written.
 */
export function createDataStore({ file, persist }) {
  const copy = file ? path.join(path.dirname(file), 'alteracoes', path.basename(file)) : null;
  let loaded = { source: null, mtime: 0, data: {} };
  const activeSource = () => (persist && fs.existsSync(copy) ? copy : file);
  const load = (source) => {
    loaded = { source, mtime: fs.statSync(source).mtimeMs, data: JSON.parse(fs.readFileSync(source, 'utf8')) };
  };
  return {
    copyPath: copy,
    usingCopy: () => Boolean(file) && persist && fs.existsSync(copy),
    // Read again when the file changes, so new data counts without restarting the portal.
    data() {
      if (!file) return {};
      const source = activeSource();
      if (source !== loaded.source || fs.statSync(source).mtimeMs !== loaded.mtime) load(source);
      return loaded.data;
    },
    commit(next) {
      if (!file) return;
      if (!persist) {
        loaded = { ...loaded, data: next };
        return;
      }
      fs.mkdirSync(path.dirname(copy), { recursive: true });
      fs.writeFileSync(`${copy}.tmp`, JSON.stringify(next, null, 2));
      fs.renameSync(`${copy}.tmp`, copy);
      load(copy);
    },
    /** Drops the saved changes and goes back to the original; tells whether there was a copy to drop. */
    reset() {
      const removed = Boolean(file) && persist && fs.existsSync(copy);
      if (removed) fs.rmSync(copy);
      loaded = { source: null, mtime: 0, data: {} };
      return removed;
    },
  };
}
