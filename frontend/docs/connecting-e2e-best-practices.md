Short version: generate a typed client from your openapi.json, keep a thin API layer in the frontend that uses those generated types, and compose UI-only fields on top (don’t change server models). Strip UI fields before sending back to the API.

Here’s a practical pattern that scales.

1) Generate types + client

Use any of these (they all work well):
	•	openapi-typescript (types) + openapi-fetch (client)
	•	openapi-client-axios
	•	Or your existing codegen if you already picked one

// api/client.ts
import createClient from 'openapi-fetch'
import type { paths, components } from './openapi' // generated

export type Schemas = components['schemas']
export const client = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL,
  headers: () => ({ Authorization: `Bearer ${yourTokenProvider()}` }),
})

2) Keep a thin API wrapper (requests/responses typed by OpenAPI)

This isolates error handling, auth, and retries.

// api/users.ts
import { client } from './client'
import type { Schemas } from './client'

export type User = Schemas['User']
export type CreateUser = Schemas['CreateUserRequest']

export async function getUser(id: string) {
  const { data, error } = await client.GET('/users/{id}', {
    params: { path: { id } },
  })
  if (error) throw error
  return data as User
}

export async function createUser(payload: CreateUser) {
  const { data, error } = await client.POST('/users', { body: payload })
  if (error) throw error
  return data as User
}

3) Use it in the UI (React Query example)

// hooks/useUser.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getUser, createUser, type User, type CreateUser } from '../api/users'

export function useUser(id: string) {
  return useQuery({ queryKey: ['user', id], queryFn: () => getUser(id) })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CreateUser) => createUser(payload),
    onSuccess: (u: User) => qc.invalidateQueries({ queryKey: ['user', u.id] }),
  })
}

4) Add UI-only fields without polluting server models

Never modify the generated types. Instead, compose:

// ui/models.ts
import type { Schemas } from '../api/client'

// fields only the frontend cares about:
type UIOnly = {
  _optimisticId?: string
  isSelected?: boolean
  isDirty?: boolean
}

export type UserVM = Schemas['User'] & UIOnly

You can now manage local state via UserVM while API functions continue to use the strict server types.

Safer send: strip UI fields before POST/PATCH

Create a tiny helper that removes any UI fields before calling the API.

// api/shape.ts
type UIOnly = { _optimisticId?: string; isSelected?: boolean; isDirty?: boolean }
const uiKeys: (keyof UIOnly)[] = ['_optimisticId', 'isSelected', 'isDirty']

export function toServer<T extends object>(obj: T): Omit<T, keyof UIOnly> {
  const clone: any = { ...obj }
  for (const k of uiKeys) delete clone[k]
  return clone
}

Use it when sending:

// somewhere in a component
import { toServer } from '../api/shape'
import { useCreateUser } from '../hooks/useUser'

createUserMutation.mutate(toServer({ name: 'Hannah', isSelected: true }))

(Alternatively: keep UI state in a parallel map { [id]: UIOnly } keyed by the server entity ID, so you never risk sending UI fields.)

5) Request vs response types

OpenAPI usually has separate schemas for inputs vs outputs. Use them so your forms don’t accidentally include server-managed fields:

type User = Schemas['User']                     // what API returns
type CreateUser = Schemas['CreateUserRequest']  // what API expects on POST
type UpdateUser = Schemas['UpdateUserRequest']  // what API expects on PATCH

6) Runtime validation (optional but recommended)

Types catch mistakes at compile time; add runtime validation for safety:
	•	If your generator gives you JSON Schemas, validate responses with ajv or transform selected payloads with zod (e.g., z.object({...}).parse(data)) at your API boundary. Fail fast and show a friendly error.

7) Versioning & regeneration
	•	Regenerate types on CI and in postinstall to avoid drift.
	•	Keep a small facade (api/*.ts) so endpoint renames or pagination shape changes don’t ripple through your React components.

8) Common gotchas and answers
	•	“Can I extend models in the frontend?”
Yes—by composition (type UIOnly + intersection types). Don’t mutate generated code or rely on declaration merging; most generators emit type aliases, which can’t be merged. Keep server DTOs pristine.
	•	“Will UI fields accidentally get sent?”
They can if you spread objects directly into body. Use toServer(...), a serializer, or store UI state separately.
	•	Optimistic updates?
Add _optimisticId/isDirty locally; on success, reconcile with the returned server entity.
	•	Discriminated unions / polymorphic schemas?
Narrow them in your API layer and expose a friendlier shape/hook to the UI.
	•	Error typing?
Centralize error normalization in the API layer so components receive a consistent { code, message, details }.

⸻

If you share which TS library you’re using for OpenAPI (e.g., openapi-fetch, openapi-client-axios, Orval, etc.), I can tailor the code to that generator’s conventions and even sketch a tiny starter API facade for your endpoints.