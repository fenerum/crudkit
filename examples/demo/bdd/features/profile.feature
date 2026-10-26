@page:/profile
Feature: Profile
  The profile page shows who is signed in and is where they sign out, for
  example before handing the computer to someone else.

  Background:
    Given Alice is signed in

  Scenario: The profile shows who is signed in
    When Alice opens her profile
    Then she sees "admin@example.com"

  Scenario: Logging out returns to the sign-in page
    When Alice opens her profile
    And she logs out
    Then she is asked to sign in
