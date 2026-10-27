@page:/login @page:/
Feature: Signing in
  Everything in the app is behind the sign-in page, so a link someone shares
  only opens for people with an account. Signing in lands on the dashboard.

  Background:
    Given Alice is not signed in

  Scenario: A wrong password is refused
    When Alice signs in with a wrong password
    Then she is told "Invalid username or password"
    And she is asked to sign in

  Scenario: Opening a page while signed out asks to sign in first
    When Alice opens the books list
    Then she is asked to sign in

  Scenario: Signing in lands on the dashboard
    When Alice signs in
    Then she is on the dashboard
    And she is shown as signed in
