@endpoint:crudkit_mcp_authorization_server @endpoint:crudkit_mcp_protected_resource
Feature: MCP clients discover how to sign in
  An MCP client only needs the server's address: two well-known documents tell
  it where to register, where to send the person to sign in, where to get
  tokens and what access it can ask for.

  Scenario: The authorization server document describes the sign-in
    When an MCP client fetches the authorization server document
    Then the document sends clients to this server to sign in, get tokens and register
    And the document lists:
      | response types         | code                              |
      | grant types            | authorization_code, refresh_token |
      | code challenge methods | S256                              |
      | client authentication  | none                              |
      | scopes                 | read, propose                     |

  Scenario: Direct writing is advertised when the server allows it
    Given the server lets MCP clients write directly
    When an MCP client fetches the authorization server document
    Then the document lists:
      | scopes | read, propose and write |

  Scenario: Proposing is only advertised when the assistant app is installed
    Given the assistant app is not installed
    When an MCP client fetches the authorization server document
    Then the document lists:
      | scopes | read |

  Scenario: The protected resource document points to the MCP endpoint
    When an MCP client fetches the protected resource document
    Then the document names the MCP endpoint as the resource, guarded by this server
    And the document lists:
      | scopes         | read, propose |
      | bearer methods | header        |

  Scenario Outline: Clients that add the MCP endpoint to the address still find the <document>
    When an MCP client fetches the <document> for the MCP endpoint
    Then the document lists:
      | scopes | read, propose |

    Examples:
      | document                      |
      | authorization server document |
      | protected resource document   |

  Scenario: Behind a proxy the configured public address is used
    Given the server's public address is "crm.example.com"
    When an MCP client fetches the authorization server document
    Then the document sends clients to "crm.example.com" to sign in, get tokens and register
