@page:/all-objects @page:not-found
Feature: Finding your way around
  Every kind of record has its own list, and the overview of all record
  types links to each of them. A broken or outdated link says so instead of
  showing an empty screen. The rail on the far left holds the workspaces,
  Home being the one everyone has; the sidebar next to it is the chosen
  workspace's menu of views and can be tucked away for more room.

  Background:
    Given Alice is signed in

  Scenario: The overview lists every kind of record
    When Alice opens the overview of all record types
    Then she sees "books", "authors" and "readings"

  Scenario: The overview leads to the list of a record type
    When Alice opens the overview of all record types
    And she follows the link "books"
    Then she is on the books list

  Scenario: A page that does not exist says so and leads home
    When Alice opens a page that does not exist
    Then she sees "Page not found"
    When she follows the link "Go home"
    Then she is on the dashboard

  Scenario: Choosing a workspace in the rail opens it with its own menu
    Given a list view "Club picks" of the readings
    And a workspace "Book club" with the view "Club picks"
    And Alice is on the dashboard
    When she chooses the workspace "Book club"
    Then the view "Club picks" is open
    And the view "Club picks" is offered in the sidebar
    But the view "All readings" is not offered in the sidebar

  Scenario: Home's menu offers every shared view
    Given a list view "Club picks" of the readings
    And a workspace "Book club" with the view "Club picks"
    And Alice is on the dashboard
    When she chooses the workspace "Book club"
    And she goes back to Home
    Then she is on the dashboard
    And the view "All readings" is offered in the sidebar

  Scenario: The sidebar can be tucked away, and stays so until brought back
    Given Alice is on the dashboard
    When she collapses the sidebar
    And she reloads the page
    Then the sidebar is hidden
    When she brings back the sidebar
    Then the view "All readings" is offered in the sidebar
