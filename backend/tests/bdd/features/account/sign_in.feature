@endpoint:token_obtain_pair @endpoint:token_refresh
Feature: Sign in
  People sign in to the app with their username and password and get a pair
  of tokens: a short-lived one the app sends with every request, and a
  longer-lived one it uses to stay signed in without asking for the password
  again.

  Background:
    Given Alice is a user without any permissions

  Scenario: Signing in with the right password gives access and the person's details
    When Alice signs in with the password "password"
    Then Alice is signed in and receives her account details

  Scenario: The token from signing in lets the app act as the person
    Given Alice signed in with the password "password"
    When Alice uses her access token to view her profile
    Then the profile is Alice's

  Scenario: Signing in with the wrong password is refused
    When Alice signs in with the password "guess"
    Then the sign-in is refused with "Invalid credentials"

  Scenario: A deactivated person cannot sign in
    Given Alice is inactive
    When Alice signs in with the password "password"
    Then the sign-in is refused with "Invalid credentials"

  Scenario: The app stays signed in by renewing its access
    Given Alice signed in with the password "password"
    When Alice signs in again with her refresh token
    Then a new access token is issued

  Scenario: A renewed access token lets the app act as the person
    Given Alice signed in with the password "password"
    And Alice signed in again with her refresh token
    When Alice uses her access token to view her profile
    Then the profile is Alice's

  Scenario: A made-up renewal is refused
    When someone renews a sign-in with a made-up refresh token
    Then it requires signing in
