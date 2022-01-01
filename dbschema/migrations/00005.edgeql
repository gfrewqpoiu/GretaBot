CREATE MIGRATION m13u5vpeew6wi2feoudww5ynotcwljfq7cbvb3z65meoknmd3tz46q
    ONTO m15ukyttkewlb3qwcg2urpdjcc4amoybzpwykqiasslv7zndqycmjq
{
  CREATE ALIAS default::Bot := (
      SELECT
          default::User
      FILTER
          (.is_bot = true)
  );
  CREATE ALIAS default::Owner := (
      SELECT
          default::User
      FILTER
          (.is_owner = true)
  );
};
