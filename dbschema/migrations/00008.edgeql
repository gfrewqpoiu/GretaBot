CREATE MIGRATION m1eqtd6jh2nxck2zd7czediy2ceeo4loiy5n4stv4ynmyqxdt7zerq
    ONTO m1ejqrtscyftpu5qxf53t6bg6wkhnio3hvfyujby46xu5paihxwbfq
{
  ALTER TYPE default::DMChannel {
      ALTER LINK user {
          CREATE CONSTRAINT std::exclusive;
      };
  };
};
