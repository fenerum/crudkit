@type:WLG
Feature: Track time spent on a record
  People can start a timer on any record, such as a customer they are working
  on, and stop it when they are done. Each person runs at most one timer at
  a time, so their tracked time never overlaps.

  Background:
    Given Alice can view customers
    And Alice can view, add and change work logs
    And a customer "Acme"
    And a customer "Globex"

  Scenario: Starting a timer on a record
    When Alice starts tracking time on "Acme"
    Then it succeeds
    And Alice is tracking time on "Acme"

  Scenario: Stopping the timer
    Given Alice is tracking time on "Acme"
    When Alice stops tracking time
    Then it succeeds
    And Alice is not tracking time

  Scenario: A person runs at most one timer at a time
    Given Alice is tracking time on "Acme"
    Then a second timer for Alice on "Globex" is refused
    And Alice is tracking time on "Acme"

 
  Scenario: Starting a second timer from the app is refused and the first keeps running
    Given Alice is tracking time on "Acme"
    When Alice starts tracking time on "Globex"
    Then it is rejected with "already tracking time"
    And Alice is tracking time on "Acme"

  Scenario: A new timer can start once the previous one is stopped
    Given Alice is tracking time on "Acme"
    And Alice stopped tracking time
    When Alice starts tracking time on "Globex"
    Then it succeeds
    And Alice is tracking time on "Globex"

  Scenario: Different people can track time at the same time
    Given Bob can view customers
    And Bob can view and add work logs
    And Alice is tracking time on "Acme"
    When Bob starts tracking time on "Acme"
    Then it succeeds
    And Bob is tracking time on "Acme"
    And Alice is tracking time on "Acme"
