Feature: Light and dark
  The app opens in its light theme. Someone who prefers a dark screen
  switches once in the sidebar, and the app stays dark for them, also after
  reloading.

  Background:
    Given Alice is signed in

  Scenario: The app opens light
    Given Alice is on the dashboard
    Then the app is light

  Scenario: Switching to dark is remembered
    Given Alice is on the dashboard
    When she switches to the dark theme
    And she reloads the page
    Then the app is dark
