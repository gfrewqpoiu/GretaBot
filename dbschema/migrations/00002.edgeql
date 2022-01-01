CREATE MIGRATION m1vi6ws6v6k6xs5rfpdmvdc62rzahbx5axfqdt2m4azryebal6rqka
    ONTO m1qnchirxfgnlqwf6hcpwrkwlvfzrzarkcaxk4mxm6khz3bgjxyfta
{
  CREATE TYPE default::UserGuildDisplayName {
      CREATE REQUIRED SINGLE LINK user -> default::User;
      CREATE REQUIRED SINGLE LINK guild -> default::Guild;
      CREATE CONSTRAINT std::exclusive ON ((.user, .guild));
      CREATE INDEX ON ((.user, .guild));
      CREATE INDEX ON (.user);
      CREATE REQUIRED PROPERTY guild_display_name -> std::str;
  };
  ALTER TYPE default::User {
      CREATE MULTI LINK guild_display_names := (.<user[IS default::UserGuildDisplayName]);
  };
};
