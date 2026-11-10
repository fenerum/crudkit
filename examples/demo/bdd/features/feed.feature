Feature: The feed of a record
  Anyone can leave a note on a record's feed, log a call or send an email from
  it, so what was said and done about a record stays with the record instead of
  in someone's inbox.

  Background:
    Given Alice is signed in
    And an author "Correspondent"

  Scenario: A posted note appears in the feed
    When Alice posts the note "Met at the book fair" on "Correspondent"
    Then she is told "Note posted"
    And the feed shows "Met at the book fair"

  Scenario: A posted note is still there after reloading
    When Alice posts the note "Met at the book fair" on "Correspondent"
    And she reloads the page
    Then the feed shows "Met at the book fair"

  Scenario: The composer offers the kinds of entries an author can have
    When Alice opens "Correspondent"
    Then the composer offers "Note", "Call" and "Email"

  Scenario: A logged call appears in the feed
    When Alice logs a call "Talked about the sequel" on "Correspondent"
    Then the feed shows the call "Talked about the sequel"

  Scenario: An email is sent from the feed with a file attached
    When Alice writes the email "Reading in May" to "author@example.com" on "Correspondent"
    And she attaches the file "programme.txt"
    And she sends it
    Then she is told "Email sent to author@example.com"
    And the feed shows the email "Reading in May" sent with the file "programme.txt"

  Scenario: Replying to an email starts one on the same subject to the same person
    Given Alice emailed "Reading in May" to "author@example.com" on "Correspondent"
    When she replies to the email "Reading in May" on "Correspondent"
    Then the email form is to "author@example.com" with the subject "Re: Reading in May"
