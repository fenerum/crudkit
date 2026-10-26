Feature: Time tracking
  Time spent on a record can be tracked from its page. The running clock
  stays in the header while moving around, so it is never forgotten.

  Background:
    Given Alice is signed in
    And Alice is not tracking time
    And a reading "Timed read"

  Scenario: Time is only tracked on a record
    When Alice opens the readings list
    Then she cannot start tracking time

  Scenario: Tracking time shows a running clock
    When Alice starts tracking time on "Timed read"
    Then she is told "Time tracking started"
    And a running clock is shown

  Scenario: The running clock follows her to other pages
    Given Alice is tracking time on "Timed read"
    When she opens "Octavia E. Butler"
    Then the running clock is for "Timed read"

  Scenario: Stopping the clock
    Given Alice is tracking time on "Timed read"
    When she stops tracking time
    Then she is told "Time tracking stopped"
    And she can start tracking time
