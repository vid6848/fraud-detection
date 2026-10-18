import { describe, expect, it } from 'vitest'
import { friendlyAuthError } from './context'

describe('friendlyAuthError', () => {
  it.each([
    [null, null],
    [{ message: 'Invalid login credentials', status: 400 }, 'Invalid email or password.'],
    [{ message: 'Email not confirmed' }, 'This account’s email is not confirmed yet.'],
    [{ message: 'whatever', status: 429 }, 'Too many attempts. Wait a minute and try again.'],
    [{ message: 'TypeError: Failed to fetch' }, 'Can’t reach the login service. Check your connection and try again.'],
    [{ message: 'something odd' }, 'Sign-in failed. Please try again.'],
  ])('%j -> %s', (error, expected) => {
    expect(friendlyAuthError(error)).toBe(expected)
  })
})
