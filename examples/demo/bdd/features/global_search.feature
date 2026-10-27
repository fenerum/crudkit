@page:/search
Feature: Searching everywhere
  One search box finds records of every type, so nobody has to know where
  something lives to get to it. It opens from the keyboard from anywhere.

  Background:
    Given Alice is signed in

  Scenario: Search finds records of every type and opens the chosen one
    When Alice searches everywhere for "Kindred"
    Then the search results include "Kindred audiobook"
    When she picks "Book club: Kindred" from the search results
    Then she is on the page of "Book club: Kindred"
    And the page is about "Book club: Kindred"

  Scenario: A type with more results than fit offers to show them all
    Given 6 readings whose names start with "Overflow"
    When Alice searches everywhere for "Overflow"
    Then the search results show 5 readings
    When she picks "Show all readings" from the search results
    Then she is on the readings list, searched for "Overflow"
    And the list has 6 records

  Scenario: The search opens from the keyboard and closes with Escape
    Given Alice is on the dashboard
    When she opens the search with the keyboard
    Then the search is ready to type in
    When she types "zzz-no-such-thing" into the search
    Then she is told "No matches"
    When she presses Escape
    Then the search is closed

  Scenario: The search page lists the matches
    When Alice searches the search page for "Kindred"
    Then she sees "Kindred audiobook" and "Book club: Kindred"
