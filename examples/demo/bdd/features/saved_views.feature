@page:/<segment>/VIW/<view> @layout:list
Feature: Saved views
  A saved view is a named, filtered way of looking at a list. Views are
  offered above the list and in the sidebar. A private view is only offered
  to the person who made it, and a view can stay out of the sidebar.

  Background:
    Given Alice is signed in

  Scenario: A new view only shows the records that match its filters
    When Alice creates the view "Finished favourites" of the readings, showing only:
      | status   | Finished |
      | priority | High     |
    Then she is on the readings list
    When she switches to the view "Finished favourites"
    Then the page is titled "Finished favourites - CrudKit Demo"
    And she sees "Book club: Kindred" and "Dispossessed notes"
    But she does not see "Anarchist utopia" and "Cities on the train"

  Scenario: A private view is offered to the person who made it
    Given Alice's private view "Just mine" of the readings
    When she opens the readings list
    Then the view "Just mine" is offered above the list
    And the view "Just mine" is offered in the sidebar

  Scenario: Someone else's private view is not offered
    When Alice opens the readings list
    Then the view "All readings" is offered above the list
    And the view "All readings" is offered in the sidebar
    But the view "Reader's private picks" is not offered above the list
    And the view "Reader's private picks" is not offered in the sidebar

  Scenario: A view can stay out of the sidebar
    Given a view "Not in the menu" of the readings that is not in the sidebar
    When Alice opens the readings list
    Then the view "Not in the menu" is offered above the list
    And the view "All readings" is offered in the sidebar
    But the view "Not in the menu" is not offered in the sidebar
