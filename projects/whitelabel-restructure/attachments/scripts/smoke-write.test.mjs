// Run with: node --test attachments/scripts/smoke-write.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {
  applyBatch,
  applyWrite,
  createDataStore,
  noEffectWarning,
  previewBatch,
  scopeState,
  syncAccessControl,
} from './smoke-write.mjs';

const AC = 'access-control';
const clone = (value) => JSON.parse(JSON.stringify(value));

const identity = (id, displayName) => ({ id, displayName, mail: `${id}@exemplo.com`, userPrincipalName: `${id}@exemplo.com` });
const role = (value, inAzure = true) => ({
  value,
  displayName: value,
  description: '',
  appRoleId: inAzure ? `r-${value}` : null,
  isEnabled: true,
  inAzure,
  usedInCode: false,
  codeRefs: [],
  userCount: 0,
  groupCount: 0,
  deletable: true,
  notDeletableReason: null,
  permission: null,
  peopleCount: 0,
});
const person = (id, name, organization, clientId = null, clientName = null) => ({
  ...identity(id, name),
  roleCount: 0,
  groupCount: 0,
  organization,
  clientId,
  clientName,
  scopeState: scopeState({ organization, clientId }, CLIENTS),
});
const group = (id, displayName, roles, members) => ({
  group: { id, displayName, description: null, memberCount: 0, roles, ownedByApp: true, deletable: true, notDeletableReason: null },
  members,
});

const CLIENTS = [{ id: 101, name: 'Cliente Alfa' }, { id: 102, name: 'Cliente Beta' }];

// Only the primary facts are written by hand; the derived ones come from the sync.
function fixture() {
  const people = [
    person('u-ana', 'Ana', 'plgn'),
    person('u-bruno', 'Bruno', 'plgn'),
    person('u-carla', 'Carla', 'plgn'),
    person('u-dora', 'Dora', 'dots', 101, 'Cliente Alfa'),
    person('u-edu', 'Edu', 'dots'),
  ];
  const mesa = group('g-mesa', 'Mesa', ['a:read'], [identity('u-ana', 'Ana'), identity('u-carla', 'Carla')]);
  const vazio = group('g-vazio', 'Vazio', [], []);
  const direct = (value, assignmentId) => [{ value, via: 'direct', groupId: null, groupName: null, assignmentId }];
  const detail = (entry, roles = []) => ({ person: identity(entry.id, entry.displayName), roles, groups: [], scope: null });
  return syncAccessControl({
    [`${AC}/settings`]: {
      organizations: [
        { value: 'plgn', label: 'Poliedro' },
        { value: 'dots', label: 'Dots' },
        { value: 'cerys', label: 'Cerys' },
        { value: 'client', label: 'Cliente' },
      ],
    },
    [`${AC}/clients`]: { clients: CLIENTS },
    [`${AC}/roles`]: { roles: ['a:read', 'a:write', 'b:read', 'c:read', 'd:read'].map((value) => role(value, value !== 'c:read')) },
    [`${AC}/people`]: { people, total: people.length, page: 1, perPage: 10, source: 'group' },
    [`${AC}/groups`]: { groups: [mesa.group, vazio.group] },
    [`${AC}/groups/g-mesa`]: mesa,
    [`${AC}/groups/g-vazio`]: vazio,
    [`${AC}/people/u-ana`]: detail(people[0], direct('b:read', 'a-1')),
    [`${AC}/people/u-bruno`]: detail(people[1], direct('d:read', 'a-2')),
    [`${AC}/people/u-carla`]: detail(people[2]),
    [`${AC}/people/u-dora`]: detail(people[3]),
    [`${AC}/people/u-edu`]: detail(people[4]),
  });
}

const get = (data, key) => data[`${AC}/${key}`];
const listed = (data, key, id) => get(data, key)[key].find((entry) => (entry.id ?? entry.value) === id);
const roleOf = (data, value) => listed(data, 'roles', value);
const holders = (data, value) => get(data, `roles/${value}/holders`);
const originsOf = (data, value, personId) => holders(data, value).people.find((holder) => holder.id === personId)?.origins.map((origin) => origin.via);
const detailOf = (data, personId) => get(data, `people/${personId}`);

const apply = (data, ...operations) => applyBatch(data, operations);
const only = (result) => {
  assert.equal(result.items.length, 1);
  return result.items[0];
};
const user = (id) => ({ kind: 'user', id });
const asGroup = (id) => ({ kind: 'group', id });

test('sync is stable: running it on consistent data changes nothing', () => {
  const data = fixture();
  assert.deepEqual(syncAccessControl(data), data);
});

test('preview and apply never change the data they receive', () => {
  const data = fixture();
  const before = clone(data);
  previewBatch(data, [{ type: 'create_group', displayName: 'Novo', description: '' }]);
  apply(data, { type: 'assign_role', role: 'b:read', principal: user('u-carla') });
  assert.deepEqual(data, before);
});

test('preview of the same operations brings the same items the apply executes', () => {
  const operations = [
    { type: 'create_role', value: 'e:read', displayName: 'E', description: '' },
    { type: 'assign_role', role: 'e:read', principal: user('u-ana') },
    { type: 'assign_role', role: 'b:read', principal: user('u-ana') },
  ];
  const preview = previewBatch(fixture(), operations);
  const applied = applyBatch(fixture(), operations);
  assert.deepEqual(applied.items.map(({ status, error, ...item }) => item), preview.items);
  assert.deepEqual(preview.items.map((item) => item.action), ['create', 'assign', 'skip']);
  assert.deepEqual(preview.summary, { create: 1, assign: 1, skip: 1 });
  assert.deepEqual(applied.summary, { ok: 2, skipped: 1 });
});

test('apply reports ok, skipped and failed, and writes only when something worked', () => {
  const data = fixture();
  const result = apply(
    data,
    { type: 'assign_role', role: 'b:read', principal: user('u-ana') },
    { type: 'assign_role', role: 'b:read', principal: { kind: 'user', email: 'ninguem@exemplo.com' } }
  );
  assert.deepEqual(result.items.map((item) => [item.action, item.status, item.error]), [
    ['skip', 'skipped', null],
    ['blocked', 'failed', 'E-mail não encontrado no diretório.'],
  ]);
  assert.deepEqual(result.summary, { skipped: 1, failed: 1 });
  assert.equal(result.data, undefined);
});

test('unknown operation is blocked', () => {
  const item = only(previewBatch(fixture(), [{ type: 'explode' }]));
  assert.equal(item.action, 'blocked');
  assert.equal(item.reason, 'Operação desconhecida.');
});

test('create_role: create, skip when it is already in Azure, and fills the missing Azure side', () => {
  const data = fixture();
  const create = { type: 'create_role', value: 'e:read', displayName: 'Ver E', description: 'Abre E' };

  const created = only(previewBatch(data, [create]));
  assert.deepEqual([created.action, created.label, created.reason], ['create', 'Criar a permissão e:read', null]);
  const next = apply(data, create).data;
  assert.equal(roleOf(next, 'e:read').inAzure, true);
  assert.equal(roleOf(next, 'e:read').displayName, 'Ver E');
  assert.deepEqual(holders(next, 'e:read'), { people: [], groups: [] });
  assert.deepEqual(get(next, 'roles').roles.map((entry) => entry.value), ['a:read', 'a:write', 'b:read', 'c:read', 'd:read', 'e:read']);

  const again = only(previewBatch(next, [create]));
  assert.deepEqual([again.action, again.reason], ['skip', 'Já existe no Azure.']);

  assert.equal(roleOf(data, 'c:read').inAzure, false);
  const fixed = apply(data, { type: 'create_role', value: 'c:read', displayName: 'C', description: '' }).data;
  assert.equal(roleOf(fixed, 'c:read').inAzure, true);
  assert.equal(get(fixed, 'roles').roles.length, 5);
});

test('create_group: create, skip when the name exists, and the group is the app\'s', () => {
  const data = fixture();
  const create = { type: 'create_group', displayName: 'Comitê', description: 'Decide' };
  assert.equal(only(previewBatch(data, [create])).action, 'create');
  const next = apply(data, create).data;
  const entry = get(next, 'groups').groups.find((candidate) => candidate.displayName === 'Comitê');
  assert.deepEqual(
    { ...entry, id: undefined },
    { id: undefined, displayName: 'Comitê', description: 'Decide', memberCount: 0, roles: [], ownedByApp: true, deletable: true, notDeletableReason: null }
  );
  assert.deepEqual(get(next, `groups/${entry.id}`), { group: entry, members: [] });

  assert.equal(entry.id, 'g-comite');

  const again = only(previewBatch(next, [{ ...create, displayName: 'comitê' }]));
  assert.deepEqual([again.action, again.reason], ['skip', 'Já existe um grupo com esse nome.']);
});

test('assign_role to a person: direct role, counters and holders', () => {
  const data = fixture();
  const operation = { type: 'assign_role', role: 'a:write', principal: user('u-bruno') };
  const item = only(previewBatch(data, [operation]));
  assert.deepEqual([item.action, item.label, item.reason], ['assign', 'Atribuir a:write para Bruno', null]);

  const next = apply(data, operation).data;
  assert.ok(detailOf(next, 'u-bruno').roles.some((entry) => entry.value === 'a:write' && entry.via === 'direct'));
  assert.equal(listed(next, 'people', 'u-bruno').roleCount, 2);
  assert.equal(roleOf(next, 'a:write').peopleCount, 1);
  assert.equal(roleOf(next, 'a:write').userCount, 1);
  assert.deepEqual(originsOf(next, 'a:write', 'u-bruno'), ['direct']);

  const again = only(previewBatch(next, [operation]));
  assert.deepEqual([again.action, again.reason], ['skip', 'Já tem.']);
});

test('assign_role by e-mail finds the person; unknown e-mail, person, group and role are blocked', () => {
  const data = fixture();
  const byMail = { type: 'assign_role', role: 'a:write', principal: { kind: 'user', email: 'U-Bruno@exemplo.com' } };
  assert.equal(only(previewBatch(data, [byMail])).action, 'assign');

  const reasons = [
    { type: 'assign_role', role: 'a:write', principal: { kind: 'user', email: 'fulano@exemplo.com' } },
    { type: 'assign_role', role: 'a:write', principal: user('u-x') },
    { type: 'assign_role', role: 'a:write', principal: asGroup('g-x') },
    { type: 'assign_role', role: 'z:read', principal: user('u-ana') },
    { type: 'assign_role', role: 'c:read', principal: user('u-ana') },
  ];
  assert.deepEqual(
    previewBatch(data, reasons).items.map((item) => [item.action, item.reason]),
    [
      ['blocked', 'E-mail não encontrado no diretório.'],
      ['blocked', 'Pessoa não encontrada.'],
      ['blocked', 'Grupo não encontrado.'],
      ['blocked', 'Permissão não encontrada.'],
      ['blocked', 'A permissão ainda não existe no Azure.'],
    ]
  );
});

test('assign_role to a group: the members inherit it, and the holders list the group', () => {
  const data = fixture();
  const next = apply(data, { type: 'assign_role', role: 'a:write', principal: asGroup('g-mesa') }).data;
  assert.deepEqual(listed(next, 'groups', 'g-mesa').roles, ['a:read', 'a:write']);
  assert.deepEqual(get(next, 'groups/g-mesa').group.roles, ['a:read', 'a:write']);
  for (const member of ['u-ana', 'u-carla']) {
    assert.deepEqual(originsOf(next, 'a:write', member), ['group']);
    assert.ok(detailOf(next, member).roles.some((entry) => entry.value === 'a:write' && entry.groupId === 'g-mesa'));
  }
  assert.equal(listed(next, 'people', 'u-carla').roleCount, 2);
  assert.equal(roleOf(next, 'a:write').peopleCount, 2);
  assert.equal(roleOf(next, 'a:write').groupCount, 1);
  assert.equal(roleOf(next, 'a:write').userCount, 0);
  assert.deepEqual(holders(next, 'a:write').groups, [{ id: 'g-mesa', displayName: 'Mesa', memberCount: 2, assignmentId: 'a-g-mesa-a:write' }]);
  assert.equal(detailOf(next, 'u-ana').groups[0].roleCount, 2);

  const again = only(previewBatch(next, [{ type: 'assign_role', role: 'a:write', principal: asGroup('g-mesa') }]));
  assert.deepEqual([again.action, again.reason], ['skip', 'Já tem.']);
});

test('add_member: member, counters, the groups of the person and the holders of the group roles', () => {
  const data = fixture();
  const operation = { type: 'add_member', group: { id: 'g-mesa' }, user: { id: 'u-bruno' } };
  const item = only(previewBatch(data, [operation]));
  assert.deepEqual([item.action, item.label, item.reason], ['add', 'Adicionar Bruno ao grupo Mesa', null]);

  const next = apply(data, operation).data;
  assert.deepEqual(get(next, 'groups/g-mesa').members.map((member) => member.id), ['u-ana', 'u-carla', 'u-bruno']);
  assert.equal(get(next, 'groups/g-mesa').group.memberCount, 3);
  assert.equal(listed(next, 'groups', 'g-mesa').memberCount, 3);
  assert.deepEqual(detailOf(next, 'u-bruno').groups, [{ id: 'g-mesa', displayName: 'Mesa', roleCount: 1, ownedByApp: true }]);
  assert.equal(listed(next, 'people', 'u-bruno').groupCount, 1);
  assert.equal(listed(next, 'people', 'u-bruno').roleCount, 2);
  assert.deepEqual(originsOf(next, 'a:read', 'u-bruno'), ['group']);
  assert.equal(holders(next, 'a:read').groups[0].memberCount, 3);
  assert.equal(roleOf(next, 'a:read').peopleCount, 3);

  const again = only(previewBatch(next, [operation]));
  assert.deepEqual([again.action, again.reason], ['skip', 'Já é membro.']);
  const byMail = only(previewBatch(data, [{ type: 'add_member', group: { name: 'vazio' }, user: { email: 'u-edu@exemplo.com' } }]));
  assert.equal(byMail.action, 'add');
  assert.equal(only(previewBatch(data, [{ type: 'add_member', group: { id: 'g-x' }, user: { id: 'u-ana' } }])).action, 'blocked');
});

test('remove_assignment undoes assign_role for a person and for a group; skips when there is nothing to remove', () => {
  const data = fixture();
  const person = { type: 'remove_assignment', role: 'b:read', principal: user('u-ana') };
  const item = only(previewBatch(data, [person]));
  assert.deepEqual([item.action, item.label], ['remove', 'Remover b:read de Ana']);
  const next = apply(data, person).data;
  assert.equal(detailOf(next, 'u-ana').roles.some((entry) => entry.value === 'b:read'), false);
  assert.equal(listed(next, 'people', 'u-ana').roleCount, 1);
  assert.equal(roleOf(next, 'b:read').peopleCount, 0);
  assert.deepEqual(holders(next, 'b:read'), { people: [], groups: [] });
  const again = only(previewBatch(next, [person]));
  assert.deepEqual([again.action, again.reason], ['skip', 'Não tem.']);

  const fromGroup = apply(data, { type: 'remove_assignment', role: 'a:read', principal: asGroup('g-mesa') }).data;
  assert.deepEqual(listed(fromGroup, 'groups', 'g-mesa').roles, []);
  assert.equal(listed(fromGroup, 'people', 'u-carla').roleCount, 0);
  assert.deepEqual(holders(fromGroup, 'a:read'), { people: [], groups: [] });
  assert.equal(roleOf(fromGroup, 'a:read').groupCount, 0);
});

test('remove_member undoes add_member; skips when the person is not a member', () => {
  const data = fixture();
  const operation = { type: 'remove_member', groupId: 'g-mesa', userId: 'u-carla' };
  const item = only(previewBatch(data, [operation]));
  assert.deepEqual([item.action, item.label], ['remove', 'Tirar Carla do grupo Mesa']);
  const next = apply(data, operation).data;
  assert.equal(listed(next, 'groups', 'g-mesa').memberCount, 1);
  assert.equal(get(next, 'groups/g-mesa').members.length, 1);
  assert.deepEqual(detailOf(next, 'u-carla').groups, []);
  assert.equal(listed(next, 'people', 'u-carla').groupCount, 0);
  assert.equal(listed(next, 'people', 'u-carla').roleCount, 0);
  assert.equal(originsOf(next, 'a:read', 'u-carla'), undefined);
  assert.equal(holders(next, 'a:read').groups[0].memberCount, 1);
  const again = only(previewBatch(next, [operation]));
  assert.deepEqual([again.action, again.reason], ['skip', 'Não é membro.']);
});

test('delete_role: the role leaves every list and detail', () => {
  const data = fixture();
  const operation = { type: 'delete_role', value: 'a:read' };
  const item = only(previewBatch(data, [operation]));
  assert.deepEqual([item.action, item.label], ['delete', 'Apagar a permissão a:read']);
  const next = apply(data, operation).data;
  assert.equal(roleOf(next, 'a:read'), undefined);
  assert.equal(holders(next, 'a:read'), undefined);
  assert.deepEqual(listed(next, 'groups', 'g-mesa').roles, []);
  assert.deepEqual(get(next, 'groups/g-mesa').group.roles, []);
  assert.deepEqual(detailOf(next, 'u-ana').roles.map((entry) => entry.value), ['b:read']);
  assert.equal(listed(next, 'people', 'u-carla').roleCount, 0);
  assert.equal(only(previewBatch(next, [operation])).action, 'blocked');

  const withDirect = apply(data, { type: 'delete_role', value: 'd:read' }).data;
  assert.deepEqual(detailOf(withDirect, 'u-bruno').roles, []);
  assert.equal(listed(withDirect, 'people', 'u-bruno').roleCount, 0);
});

test('delete_group: the group leaves every list and detail, and so do its inherited roles', () => {
  const data = fixture();
  const operation = { type: 'delete_group', groupId: 'g-mesa' };
  const item = only(previewBatch(data, [operation]));
  assert.deepEqual([item.action, item.label], ['delete', 'Apagar o grupo Mesa']);
  const next = apply(data, operation).data;
  assert.equal(listed(next, 'groups', 'g-mesa'), undefined);
  assert.equal(get(next, 'groups/g-mesa'), undefined);
  assert.deepEqual(detailOf(next, 'u-ana').groups, []);
  assert.deepEqual(detailOf(next, 'u-ana').roles.map((entry) => entry.value), ['b:read']);
  assert.equal(listed(next, 'people', 'u-ana').groupCount, 0);
  assert.equal(listed(next, 'people', 'u-carla').roleCount, 0);
  assert.deepEqual(holders(next, 'a:read'), { people: [], groups: [] });
  assert.equal(roleOf(next, 'a:read').groupCount, 0);
  assert.equal(only(previewBatch(next, [operation])).action, 'blocked');
});

test('copy_assignments: one assign for each person and group that has the source; skip for who has the target', () => {
  const data = apply(fixture(), { type: 'assign_role', role: 'a:read', principal: user('u-bruno') }).data;
  const operation = { type: 'copy_assignments', from: 'a:read', to: 'b:read' };
  const preview = previewBatch(data, [operation]);
  assert.deepEqual(preview.items.map((item) => [item.index, item.action, item.label, item.reason]), [
    [0, 'assign', 'Atribuir b:read para Bruno, que tem a:read', null],
    [0, 'assign', 'Atribuir b:read para o grupo Mesa, que tem a:read', null],
  ]);
  const next = apply(data, operation).data;
  assert.deepEqual(originsOf(next, 'b:read', 'u-bruno'), ['direct']);
  assert.deepEqual(originsOf(next, 'b:read', 'u-carla'), ['group']);
  assert.deepEqual(listed(next, 'groups', 'g-mesa').roles, ['a:read', 'b:read']);

  const toAna = previewBatch(fixture(), [{ type: 'copy_assignments', from: 'b:read', to: 'a:read' }]);
  assert.deepEqual(toAna.items.map((item) => [item.action, item.reason]), [['assign', null]]);
  const again = previewBatch(next, [operation]);
  assert.deepEqual(again.items.map((item) => [item.action, item.reason]), [['skip', 'Já tem.'], ['skip', 'Já tem.']]);

  assert.equal(only(previewBatch(data, [{ type: 'copy_assignments', from: 'a:write', to: 'b:read' }])).reason, 'Ninguém tem a permissão a:write.');
  assert.equal(only(previewBatch(data, [{ type: 'copy_assignments', from: 'c:read', to: 'b:read' }])).action, 'skip');
  assert.equal(only(previewBatch(data, [{ type: 'copy_assignments', from: 'a:read', to: 'c:read' }])).action, 'blocked');
});

test('scopeState: internal is ok, no organization, partner with no client, client out of the list', () => {
  assert.equal(scopeState({ organization: 'plgn', clientId: null }, CLIENTS), 'ok');
  assert.equal(scopeState({ organization: 'plgn', clientId: 999 }, CLIENTS), 'ok');
  assert.equal(scopeState({ organization: null, clientId: null }, CLIENTS), 'no-organization');
  assert.equal(scopeState({ organization: null, clientId: 101 }, CLIENTS), 'no-organization');
  assert.equal(scopeState({ organization: 'dots', clientId: null }, CLIENTS), 'no-client');
  assert.equal(scopeState({ organization: 'dots', clientId: 999 }, CLIENTS), 'invalid-client');
  assert.equal(scopeState({ organization: 'dots', clientId: 101 }, CLIENTS), 'ok');
  assert.equal(scopeState({ organization: 'dots', clientId: 999 }, null), 'ok');
});

test('set_person_scope: update, label, list and detail, each state, and skip when nothing changes', () => {
  const data = fixture();
  const toPartner = { type: 'set_person_scope', user: { id: 'u-ana' }, organization: 'dots', clientId: 102 };
  const item = only(previewBatch(data, [toPartner]));
  assert.deepEqual([item.action, item.label, item.reason], ['update', 'Mudar Ana para a organização Dots e o cliente Cliente Beta', null]);

  const next = apply(data, toPartner).data;
  const expected = { organization: 'dots', clientId: 102, clientName: 'Cliente Beta' };
  assert.deepEqual(
    { organization: listed(next, 'people', 'u-ana').organization, clientId: listed(next, 'people', 'u-ana').clientId, clientName: listed(next, 'people', 'u-ana').clientName },
    expected
  );
  assert.equal(listed(next, 'people', 'u-ana').scopeState, 'ok');
  assert.deepEqual(detailOf(next, 'u-ana').scope, { ...expected, state: 'ok' });
  const again = only(previewBatch(next, [toPartner]));
  assert.deepEqual([again.action, again.reason], ['skip', 'Já está com essa organização e esse cliente.']);

  const states = [
    [{ organization: 'plgn', clientId: 102 }, 'ok', null],
    [{ organization: 'dots', clientId: null }, 'no-client', null],
    [{ organization: 'dots', clientId: 999 }, 'invalid-client', null],
    [{ organization: null, clientId: null }, 'no-organization', null],
  ];
  for (const [scope, state] of states) {
    const result = apply(next, { type: 'set_person_scope', user: { id: 'u-ana' }, ...scope }).data;
    assert.equal(listed(result, 'people', 'u-ana').scopeState, state);
    assert.equal(detailOf(result, 'u-ana').scope.state, state);
    if (scope.organization === 'plgn') {
      assert.equal(listed(result, 'people', 'u-ana').clientId, null);
      assert.equal(listed(result, 'people', 'u-ana').clientName, null);
    }
  }
  assert.equal(listed(apply(next, { type: 'set_person_scope', user: { id: 'u-ana' }, organization: 'dots', clientId: 999 }).data, 'people', 'u-ana').clientName, null);

  const byMail = only(previewBatch(data, [{ type: 'set_person_scope', user: { email: 'u-bruno@exemplo.com' }, organization: 'cerys', clientId: 101 }]));
  assert.equal(byMail.action, 'update');
  assert.equal(only(previewBatch(data, [{ type: 'set_person_scope', user: { id: 'u-x' }, organization: 'plgn', clientId: null }])).action, 'blocked');
});

test('set_person_scope shows up in the without-scope people the page filters', () => {
  const next = apply(fixture(), { type: 'set_person_scope', user: { id: 'u-bruno' }, organization: 'dots', clientId: null }).data;
  const withoutScope = get(next, 'people').people.filter((entry) => entry.scopeState && entry.scopeState !== 'ok').map((entry) => entry.id);
  assert.deepEqual(withoutScope, ['u-bruno', 'u-edu']);
});

test('what a batch creates is there for the next operations of the same batch', () => {
  const data = fixture();
  const operations = [
    { type: 'create_group', displayName: 'Novo', description: '' },
    { type: 'create_role', value: 'e:read', displayName: 'E', description: '' },
    { type: 'assign_role', role: 'e:read', principal: { kind: 'group', name: 'Novo' } },
    { type: 'add_member', group: { name: 'Novo' }, user: { id: 'u-edu' } },
  ];
  const preview = previewBatch(data, operations);
  assert.deepEqual(preview.items.map((item) => item.action), ['create', 'create', 'assign', 'add']);
  const next = apply(data, ...operations).data;
  assert.deepEqual(originsOf(next, 'e:read', 'u-edu'), ['group']);
  assert.equal(roleOf(next, 'e:read').peopleCount, 1);
});

test('applyWrite: the batch routes answer by the table, 400 without operations, null elsewhere in access-control', () => {
  const data = fixture();
  const operations = [{ type: 'assign_role', role: 'a:write', principal: user('u-bruno') }];

  const preview = applyWrite(data, 'POST', `${AC}/batch/preview`, { operations });
  assert.equal(preview.status, 200);
  assert.equal(preview.data, undefined);
  assert.deepEqual(preview.body.summary, { assign: 1 });

  const applied = applyWrite(data, 'POST', `${AC}/batch/apply`, { operations, confirm: 'REMOVER' });
  assert.deepEqual(applied.body.summary, { ok: 1 });
  assert.equal(roleOf(applied.data, 'a:write').peopleCount, 1);
  assert.equal(Object.hasOwn(applied.body, 'data'), false);

  assert.equal(applyWrite(data, 'POST', `${AC}/batch/apply`, {}).status, 400);
  assert.equal(applyWrite(data, 'DELETE', `${AC}/groups/g-mesa`, undefined), null);
  assert.equal(applyWrite(data, 'PATCH', `${AC}/people/u-ana`, { displayName: 'X' }), null);
  assert.equal(applyWrite({ [`${AC}/batch/preview`]: { items: [], summary: {} } }, 'POST', `${AC}/batch/preview`, { operations }), null);
});

test('generic lists: POST appends with a new id in an array, in records and in items, and the counters follow', () => {
  const array = applyWrite({ tarefas: [{ id: 1 }, { id: 4 }] }, 'POST', 'tarefas', { nome: 'x' });
  assert.deepEqual([array.status, array.body], [201, { nome: 'x', id: 5 }]);
  assert.deepEqual(array.data.tarefas, [{ id: 1 }, { id: 4 }, { nome: 'x', id: 5 }]);

  const records = { pagination: { page: 1, total_count: 40 }, records: [{ id: 'a' }] };
  const inRecords = applyWrite({ lotes: records }, 'POST', 'lotes', { nome: 'y' });
  assert.deepEqual(inRecords.data.lotes.records.map((entry) => entry.id), ['a', 'novo-2']);
  assert.equal(inRecords.data.lotes.pagination.total_count, 41);
  assert.equal(inRecords.data.lotes.pagination.page, 1);

  const items = { items: [{ key: 'PT-101' }, { key: 'PT-108' }], total: 8, limit: 20 };
  const inItems = applyWrite({ 'pre-trade/requests': items }, 'POST', 'pre-trade/requests', { type: 'compra', key: 'ignorada' });
  assert.deepEqual(inItems.body, { type: 'compra', key: 'PT-109' });
  assert.equal(inItems.data['pre-trade/requests'].total, 9);
  assert.equal(inItems.data['pre-trade/requests'].limit, 20);
  assert.deepEqual(items.items, [{ key: 'PT-101' }, { key: 'PT-108' }]);

  const empty = applyWrite({ vazio: [] }, 'POST', 'vazio', { a: 1 });
  assert.deepEqual(empty.body, { a: 1, id: 'novo-1' });
});

test('generic lists: PATCH and PUT merge into the item and into its detail', () => {
  const data = {
    'tarefas': { records: [{ id: 'a', nome: 'um', fixo: true }, { id: 'b', nome: 'dois' }], pagination: { total_count: 2 } },
    'tarefas/a': { id: 'a', nome: 'um', passos: [1] },
  };
  const patched = applyWrite(data, 'PATCH', 'tarefas/a', { nome: 'novo', id: 'outro' });
  assert.equal(patched.status, 200);
  assert.deepEqual(patched.data.tarefas.records[0], { id: 'a', nome: 'novo', fixo: true });
  assert.deepEqual(patched.data['tarefas/a'], { id: 'a', nome: 'novo', passos: [1] });
  assert.deepEqual(patched.body, patched.data['tarefas/a']);
  assert.equal(patched.data.tarefas.pagination.total_count, 2);

  const put = applyWrite(data, 'PUT', 'tarefas/b', { nome: 'dois!' });
  assert.deepEqual(put.data.tarefas.records[1], { id: 'b', nome: 'dois!' });
  assert.deepEqual(put.body, { id: 'b', nome: 'dois!' });
  assert.equal(put.data['tarefas/b'], undefined);

  const byKey = applyWrite({ 'pre/req': { items: [{ key: 'PT-1', stage: 'a' }] } }, 'PATCH', 'pre/req/PT-1', { stage: 'b' });
  assert.deepEqual(byKey.data['pre/req'].items, [{ key: 'PT-1', stage: 'b' }]);

  const numeric = applyWrite({ lista: [{ id: 7, n: 1 }] }, 'PATCH', 'lista/7', { n: 2 });
  assert.deepEqual(numeric.data.lista, [{ id: 7, n: 2 }]);

  const detailOnly = applyWrite({ 'x/y': { a: 1 } }, 'PATCH', 'x/y', { b: 2 });
  assert.deepEqual(detailOnly.data['x/y'], { a: 1, b: 2 });
});

test('generic lists: DELETE takes the item from the list and drops the detail, and the counters follow', () => {
  const data = {
    'pre-trade/requests': { items: [{ key: 'PT-101' }, { key: 'PT-102' }], total: 2 },
    'pre-trade/requests/PT-101': { key: 'PT-101', detalhe: true },
    'pre-trade/requests/PT-101/history': [],
  };
  const result = applyWrite(data, 'DELETE', 'pre-trade/requests/PT-101', undefined);
  assert.equal(result.status, 200);
  assert.deepEqual(result.data['pre-trade/requests'], { items: [{ key: 'PT-102' }], total: 1 });
  assert.equal('pre-trade/requests/PT-101' in result.data, false);
  assert.deepEqual(result.body, { key: 'PT-101' });
  assert.ok(data['pre-trade/requests/PT-101']);

  const paged = applyWrite({ l: { records: [{ id: 1 }], pagination: { total_count: 1 } } }, 'DELETE', 'l/1');
  assert.deepEqual(paged.data.l, { records: [], pagination: { total_count: 0 } });
});

test('writes with no rule return null, and the warning names the method and the path', () => {
  assert.equal(applyWrite({ a: [{ id: 1 }] }, 'DELETE', 'a/2'), null);
  assert.equal(applyWrite({ a: [{ id: 1 }] }, 'PATCH', 'a/2', { x: 1 }), null);
  assert.equal(applyWrite({ a: [{ id: 1 }] }, 'PATCH', 'a/1', undefined), null);
  assert.equal(applyWrite({}, 'POST', 'nada', { x: 1 }), null);
  assert.equal(applyWrite({ obj: { a: 1 } }, 'POST', 'obj', { x: 1 }), null);
  assert.equal(applyWrite({ lista: ['x'] }, 'POST', 'lista', { x: 1 }), null);
  assert.equal(applyWrite({ a: [] }, 'POST', 'a', undefined), null);
  assert.equal(applyWrite({ a: [] }, 'GET', 'a', undefined), null);
  assert.equal(noEffectWarning('POST', 'a/b'), 'escrita sem efeito: POST a/b');
});

test('POSTs that only search do not put the query in the list', () => {
  const data = { 'pre-trade/assets': { records: [{ id: 1 }], pagination: { total_count: 1 } } };
  assert.equal(applyWrite(data, 'POST', 'pre-trade/assets', { ticker: 'ABC' }), null);
  assert.equal(applyWrite({ 'pre-trade/investor-vehicles': [] }, 'POST', 'pre-trade/investor-vehicles', { partial_name: 'x' }), null);
});

function withTempDir(run) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'smoke-write-'));
  try {
    return run(dir);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

test('store: changes go to alteracoes/ next to the file, survive a restart and win over the original', () => {
  withTempDir((dir) => {
    const file = path.join(dir, 'dados.json');
    fs.writeFileSync(file, JSON.stringify({ lista: [{ id: 1 }] }));
    const store = createDataStore({ file, persist: true });
    assert.equal(store.copyPath, path.join(dir, 'alteracoes', 'dados.json'));
    assert.deepEqual(store.data(), { lista: [{ id: 1 }] });
    assert.equal(store.usingCopy(), false);

    store.commit(applyWrite(store.data(), 'POST', 'lista', { nome: 'novo' }).data);
    assert.equal(store.usingCopy(), true);
    assert.deepEqual(JSON.parse(fs.readFileSync(store.copyPath, 'utf8')), { lista: [{ id: 1 }, { nome: 'novo', id: 2 }] });
    assert.deepEqual(JSON.parse(fs.readFileSync(file, 'utf8')), { lista: [{ id: 1 }] });

    const restarted = createDataStore({ file, persist: true });
    assert.deepEqual(restarted.data().lista.length, 2);
    assert.equal(restarted.usingCopy(), true);
  });
});

test('store: reset drops the copy and goes back to the original, and is harmless without one', () => {
  withTempDir((dir) => {
    const file = path.join(dir, 'dados.json');
    fs.writeFileSync(file, JSON.stringify({ lista: [{ id: 1 }] }));
    const store = createDataStore({ file, persist: true });
    assert.equal(store.reset(), false);
    store.commit({ lista: [] });
    assert.deepEqual(store.data(), { lista: [] });

    assert.equal(store.reset(), true);
    assert.equal(fs.existsSync(store.copyPath), false);
    assert.deepEqual(store.data(), { lista: [{ id: 1 }] });
    assert.equal(createDataStore({ file, persist: true }).data().lista.length, 1);
  });
});

test('store: the smoke (no persist) keeps changes in memory, never writes, and ignores an existing copy', () => {
  withTempDir((dir) => {
    const file = path.join(dir, 'dados.json');
    fs.writeFileSync(file, JSON.stringify({ lista: [{ id: 1 }] }));
    const saved = createDataStore({ file, persist: true });
    saved.commit({ lista: [] });

    const smoke = createDataStore({ file, persist: false });
    assert.deepEqual(smoke.data(), { lista: [{ id: 1 }] });
    smoke.commit({ lista: [{ id: 1 }, { id: 2 }] });
    assert.equal(smoke.data().lista.length, 2);
    assert.deepEqual(JSON.parse(fs.readFileSync(saved.copyPath, 'utf8')), { lista: [] });
    assert.equal(smoke.reset(), false);
    assert.equal(fs.existsSync(saved.copyPath), true);
    assert.equal(smoke.data().lista.length, 1);

    fs.rmSync(path.join(dir, 'alteracoes'), { recursive: true });
    const clean = createDataStore({ file, persist: false });
    clean.commit({ lista: [] });
    assert.equal(fs.existsSync(path.join(dir, 'alteracoes')), false);
  });
});

test('store: without a file there is nothing to read or write', () => {
  const store = createDataStore({ file: undefined, persist: true });
  assert.deepEqual(store.data(), {});
  store.commit({ a: 1 });
  assert.equal(store.reset(), false);
  assert.deepEqual(store.data(), {});
});
