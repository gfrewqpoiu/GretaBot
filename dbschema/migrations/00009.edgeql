CREATE MIGRATION m1rar3irt5aziikd5yx2kltht6se5idl4huiwngsi4ftvskigmi5cq
    ONTO m1eqtd6jh2nxck2zd7czediy2ceeo4loiy5n4stv4ynmyqxdt7zerq
{
  ALTER TYPE default::User {
      CREATE SINGLE LINK dm_channel := (.<user[IS default::DMChannel]);
  };
};
