CREATE MIGRATION m15ukyttkewlb3qwcg2urpdjcc4amoybzpwykqiasslv7zndqycmjq
    ONTO m1c3dhxm5fxfbsb4dxlconpsnytao2x47pp2bqazppyx4s4xdh7ahq
{
  ALTER TYPE default::Guild {
      ALTER LINK users {
          RENAME TO members;
      };
  };
};
