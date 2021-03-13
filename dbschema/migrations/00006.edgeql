CREATE MIGRATION m1ktjlzmgqaf4errf2ab4lxext37xxgouuaokivj43s6nq7vtdoyhq
    ONTO m1qalnignwwao3azkexokf7tyuvbblecdwzhsbml7jst4cjv2eczlq
{
  ALTER TYPE default::User {
      CREATE MULTI LINK guilds := (.<users[IS default::Guild]);
  };
};
