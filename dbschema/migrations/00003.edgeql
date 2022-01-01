CREATE MIGRATION m1c3dhxm5fxfbsb4dxlconpsnytao2x47pp2bqazppyx4s4xdh7ahq
    ONTO m1vi6ws6v6k6xs5rfpdmvdc62rzahbx5axfqdt2m4azryebal6rqka
{
  ALTER TYPE default::Guild {
      ALTER LINK users {
          CREATE PROPERTY guild_nickname -> default::bounded_str;
      };
  };
  ALTER TYPE default::User {
      DROP LINK guild_display_names;
  };
  DROP TYPE default::UserGuildDisplayName;
};
